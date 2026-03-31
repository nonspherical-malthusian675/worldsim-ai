"""Data ingestion pipeline: buffer, transform, and orchestrate multiple sources."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from worldsim.io.sources import DataSource, SensorReading

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Buffer (ring buffer)
# ---------------------------------------------------------------------------

class DataBuffer:
    """Fixed-capacity ring buffer for recent sensor readings."""

    def __init__(self, max_size: int = 10000) -> None:
        self.max_size = max_size
        self._buffer: Deque[SensorReading] = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def put(self, reading: SensorReading) -> None:
        with self._lock:
            self._buffer.append(reading)

    def put_many(self, readings: List[SensorReading]) -> None:
        with self._lock:
            for r in readings:
                self._buffer.append(r)

    def get_latest(self, sensor_id: Optional[str] = None) -> Optional[SensorReading]:
        with self._lock:
            if sensor_id is None:
                return self._buffer[-1] if self._buffer else None
            for r in reversed(self._buffer):
                if r.sensor_id == sensor_id:
                    return r
            return None

    def get_recent(self, seconds: float = 60.0) -> List[SensorReading]:
        cutoff = time.time() - seconds
        with self._lock:
            return [r for r in self._buffer if r.timestamp >= cutoff]

    def get_by_source(self, source: str) -> List[SensorReading]:
        with self._lock:
            return [r for r in self._buffer if r.source == source]

    @property
    def size(self) -> int:
        return len(self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()


# ---------------------------------------------------------------------------
# Data Transformer
# ---------------------------------------------------------------------------

@dataclass
class TransformConfig:
    """Configuration for a single sensor-to-entity mapping."""
    sensor_id: str
    entity_id: str
    unit_from: str = ""
    unit_to: str = ""
    scale: float = 1.0
    offset: float = 0.0
    filter_min: Optional[float] = None
    filter_max: Optional[float] = None


class DataTransformer:
    """Converts raw sensor data into simulation state updates.

    Supports unit conversion, scaling, filtering, and sensor-to-entity mapping.
    """

    def __init__(self) -> None:
        self._mappings: Dict[str, TransformConfig] = {}
        self._unit_converters: Dict[Tuple[str, str], Callable[[float], float]] = {}
        self._register_default_conversions()

    def _register_default_conversions(self) -> None:
        c = self._unit_converters
        # Temperature
        c[("celsius", "fahrenheit")] = lambda v: v * 9.0 / 5.0 + 32.0
        c[("fahrenheit", "celsius")] = lambda v: (v - 32.0) * 5.0 / 9.0
        c[("celsius", "kelvin")] = lambda v: v + 273.15
        c[("kelvin", "celsius")] = lambda v: v - 273.15

    def add_mapping(self, config: TransformConfig) -> None:
        self._mappings[config.sensor_id] = config

    def add_mappings(self, configs: List[TransformConfig]) -> None:
        for c in configs:
            self._mappings[c.sensor_id] = c

    def transform(self, reading: SensorReading) -> Optional[Dict[str, Any]]:
        """Transform a sensor reading into a simulation state update dict."""
        config = self._mappings.get(reading.sensor_id)
        value = reading.value
        if value is None:
            return None

        # Unit conversion
        if config and config.unit_from and config.unit_to and config.unit_from != config.unit_to:
            converter = self._unit_converters.get((config.unit_from, config.unit_to))
            if converter:
                value = converter(float(value))

        # Scaling
        if config:
            value = value * config.scale + config.offset
            # Filtering
            if config.filter_min is not None and value < config.filter_min:
                return None
            if config.filter_max is not None and value > config.filter_max:
                return None

        entity_id = config.entity_id if config else reading.sensor_id
        return {
            "entity_id": entity_id,
            "sensor_id": reading.sensor_id,
            "timestamp": reading.timestamp,
            "value": value,
            "source": reading.source,
            "metadata": reading.metadata,
        }

    def transform_batch(self, readings: List[SensorReading]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for r in readings:
            t = self.transform(r)
            if t is not None:
                results.append(t)
        return results


# ---------------------------------------------------------------------------
# Data Ingestion Manager
# ---------------------------------------------------------------------------

class DataIngestionManager:
    """Orchestrates multiple data sources through a validation → transform → buffer pipeline."""

    def __init__(self, buffer_size: int = 10000) -> None:
        self._sources: Dict[str, DataSource] = {}
        self.buffer = DataBuffer(max_size=buffer_size)
        self.transformer = DataTransformer()
        self._threads: Dict[str, threading.Thread] = {}
        self._running = False
        self._lock = threading.Lock()
        self._on_data_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def register_source(self, name: str, source: DataSource) -> None:
        """Register a data source with a given name."""
        self._sources[name] = source

    def unregister_source(self, name: str) -> None:
        """Remove a data source."""
        self._sources.pop(name, None)

    def on_data(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback to receive transformed data."""
        self._on_data_callbacks.append(callback)

    def start_all(self) -> None:
        """Connect and start reading from all registered sources."""
        with self._lock:
            if self._running:
                return
            self._running = True

        for name, source in self._sources.items():
            source.connect()
            t = threading.Thread(target=self._read_loop, args=(name, source), daemon=True)
            self._threads[name] = t
            t.start()
        logger.info("Started ingestion for %d sources", len(self._sources))

    def _read_loop(self, name: str, source: DataSource) -> None:
        try:
            for reading in source.read():
                if not self._running:
                    break
                # Validate
                if reading.value is None and reading.metadata.get("status") != "failure":
                    continue
                # Buffer
                self.buffer.put(reading)
                # Transform
                transformed = self.transformer.transform(reading)
                if transformed:
                    for cb in self._on_data_callbacks:
                        try:
                            cb(transformed)
                        except Exception:
                            logger.exception("Ingestion callback error")
        except Exception:
            logger.exception("[%s] Read loop crashed", name)

    def stop_all(self) -> None:
        """Stop all sources and join threads."""
        self._running = False
        for name, source in self._sources.items():
            try:
                source.disconnect()
            except Exception:
                logger.exception("[%s] Error disconnecting", name)
        for name, t in self._threads.items():
            t.join(timeout=5)
        self._threads.clear()
        logger.info("Stopped all ingestion sources")

    @property
    def sources(self) -> Dict[str, DataSource]:
        return dict(self._sources)
