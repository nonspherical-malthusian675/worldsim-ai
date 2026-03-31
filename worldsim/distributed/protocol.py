"""gRPC-like protocol definitions using dataclasses.

These mirror what protobuf messages would look like, allowing the system
to function without running ``protoc``.
"""

from __future__ import annotations

import pickle
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Message types (protobuf-like dataclasses)
# ---------------------------------------------------------------------------

@dataclass
class AgentUpdate:
    agent_id: str = ""
    position: List[float] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    removed: bool = False


@dataclass
class SimState:
    """Represents simulation state for syncing between nodes."""
    tick: int = 0
    node_id: str = ""
    agent_updates: List[AgentUpdate] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    checksum: str = ""


@dataclass
class SyncRequest:
    source_node: str = ""
    target_node: str = ""
    tick: int = 0
    state: Optional[SimState] = None


@dataclass
class SyncResponse:
    source_node: str = ""
    target_node: str = ""
    tick: int = 0
    accepted: bool = True
    state: Optional[SimState] = None
    error: str = ""


@dataclass
class Heartbeat:
    node_id: str = ""
    timestamp: float = 0.0
    agent_count: int = 0
    load: float = 0.0
    status: str = "alive"  # alive | degraded | stopping


@dataclass
class MigrationRequest:
    source_node: str = ""
    target_node: str = ""
    agent_ids: List[str] = field(default_factory=list)


@dataclass
class MigrationAck:
    source_node: str = ""
    target_node: str = ""
    agent_ids: List[str] = field(default_factory=list)
    success: bool = True
    error: str = ""


# ---------------------------------------------------------------------------
# Serializer
# ---------------------------------------------------------------------------

class MessageSerializer:
    """Serialize/deserialize messages using pickle + zlib compression."""

    @staticmethod
    def serialize(msg: Any) -> bytes:
        """Serialize a message to compressed bytes."""
        data = pickle.dumps(msg, protocol=pickle.HIGHEST_PROTOCOL)
        return zlib.compress(data)

    @staticmethod
    def deserialize(data: bytes) -> Any:
        """Deserialize compressed bytes back to a message."""
        return pickle.loads(zlib.decompress(data))

    @staticmethod
    def serialize_batch(messages: List[Any]) -> bytes:
        """Serialize a list of messages into a single compressed payload."""
        data = pickle.dumps(messages, protocol=pickle.HIGHEST_PROTOCOL)
        return zlib.compress(data)

    @staticmethod
    def deserialize_batch(data: bytes) -> List[Any]:
        """Deserialize a batch of messages."""
        return pickle.loads(zlib.decompress(data))
