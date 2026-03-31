"""Plugin marketplace client — discover, install, and manage plugins."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PluginMetadata:
    """Metadata for a marketplace plugin."""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    min_worldsim_version: str = "0.1.0"
    downloads: int = 0
    rating: float = 0.0
    source_url: Optional[str] = None
    installed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "min_worldsim_version": self.min_worldsim_version,
            "downloads": self.downloads,
            "rating": self.rating,
            "source_url": self.source_url,
            "installed": self.installed,
        }


class PluginRegistry:
    """
    Local plugin registry at ~/.worldsim/plugins/
    
    Tracks installed plugins and their metadata.
    """

    def __init__(self, registry_dir: Optional[str] = None):
        self._dir = Path(registry_dir) if registry_dir else Path.home() / ".worldsim" / "plugins"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._dir / "index.json"
        self._installed: Dict[str, PluginMetadata] = {}
        self._load_index()

    def _load_index(self) -> None:
        if self._index_file.exists():
            try:
                data = json.loads(self._index_file.read_text())
                for pid, meta in data.items():
                    self._installed[pid] = PluginMetadata(**meta, installed=True)
            except Exception as e:
                logger.warning(f"Failed to load plugin index: {e}")

    def _save_index(self) -> None:
        data = {pid: m.to_dict() for pid, m in self._installed.items()}
        self._index_file.write_text(json.dumps(data, indent=2))

    def install(self, metadata: PluginMetadata, source_path: Optional[str] = None) -> bool:
        """Register a plugin as installed."""
        plugin_dir = self._dir / metadata.plugin_id
        plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # Save metadata
        meta_path = plugin_dir / "metadata.json"
        meta_path.write_text(json.dumps(metadata.to_dict(), indent=2))
        
        if source_path:
            import shutil
            shutil.copy2(source_path, plugin_dir / Path(source_path).name)
        
        metadata.installed = True
        self._installed[metadata.plugin_id] = metadata
        self._save_index()
        logger.info(f"Plugin installed: {metadata.name} v{metadata.version}")
        return True

    def uninstall(self, plugin_id: str) -> bool:
        if plugin_id not in self._installed:
            return False
        plugin_dir = self._dir / plugin_id
        if plugin_dir.exists():
            import shutil
            shutil.rmtree(plugin_dir)
        del self._installed[plugin_id]
        self._save_index()
        logger.info(f"Plugin uninstalled: {plugin_id}")
        return True

    def is_installed(self, plugin_id: str) -> bool:
        return plugin_id in self._installed

    def get_installed(self) -> List[PluginMetadata]:
        return list(self._installed.values())

    def get_plugin_path(self, plugin_id: str) -> Optional[str]:
        plugin_dir = self._dir / plugin_id
        if plugin_dir.exists():
            # Find .py files
            py_files = list(plugin_dir.glob("*.py"))
            return str(py_files[0]) if py_files else None
        return None


class MarketplaceAPI:
    """
    Plugin marketplace client.
    
    In a real deployment, this would connect to a remote API.
    For now, it manages a local catalog and can be extended to a real server.
    """

    def __init__(self, registry: Optional[PluginRegistry] = None):
        self._registry = registry or PluginRegistry()
        self._catalog: Dict[str, PluginMetadata] = {}
        self._load_built_in_catalog()

    def _load_built_in_catalog(self) -> None:
        """Load built-in plugin catalog."""
        builtins = [
            PluginMetadata(
                plugin_id="logging", name="Logging Plugin", version="1.0.0",
                description="Configurable file/console logging for all simulation events",
                author="WorldSim AI", tags=["logging", "monitoring"],
            ),
            PluginMetadata(
                plugin_id="metrics_export", name="Prometheus Metrics", version="1.0.0",
                description="Export simulation metrics in Prometheus format",
                author="WorldSim AI", tags=["metrics", "monitoring", "prometheus"],
            ),
            PluginMetadata(
                plugin_id="slack_notify", name="Slack Notifications", version="1.0.0",
                description="Send simulation alerts to Slack via webhook",
                author="WorldSim AI", tags=["notifications", "alerts", "slack"],
            ),
            PluginMetadata(
                plugin_id="csv_export", name="CSV Data Export", version="1.0.0",
                description="Export simulation results to CSV files automatically",
                author="WorldSim AI", tags=["export", "data", "csv"],
            ),
            PluginMetadata(
                plugin_id="heatmap_gen", name="Heatmap Generator", version="1.0.0",
                description="Generate heatmap images from simulation data",
                author="WorldSim AI", tags=["visualization", "heatmap", "images"],
            ),
            PluginMetadata(
                plugin_id="scenario_scheduler", name="Scenario Scheduler", version="1.0.0",
                description="Schedule scenarios to run at specific times (cron-like)",
                author="WorldSim AI", tags=["scheduling", "automation"],
            ),
            PluginMetadata(
                plugin_id="rest_connector", name="REST Connector", version="1.0.0",
                description="Connect external REST APIs as simulation data sources",
                author="WorldSim AI", tags=["integration", "api", "iot"],
            ),
        ]
        for p in builtins:
            p.installed = self._registry.is_installed(p.plugin_id)
            self._catalog[p.plugin_id] = p

    def list_available(self) -> List[PluginMetadata]:
        return sorted(self._catalog.values(), key=lambda p: p.name)

    def search(self, query: str) -> List[PluginMetadata]:
        query = query.lower()
        return [p for p in self._catalog.values()
                if query in p.name.lower() or query in p.description.lower()
                or any(query in t for t in p.tags)]

    def get_plugin(self, plugin_id: str) -> Optional[PluginMetadata]:
        return self._catalog.get(plugin_id)

    def install_plugin(self, plugin_id: str) -> Dict[str, Any]:
        """Install a plugin from the catalog."""
        meta = self._catalog.get(plugin_id)
        if not meta:
            return {"success": False, "error": "plugin_not_found"}
        
        # For built-in plugins, they're already in the codebase
        success = self._registry.install(meta)
        meta.installed = success
        return {"success": success, "plugin": meta.name, "version": meta.version}

    def uninstall_plugin(self, plugin_id: str) -> Dict[str, Any]:
        success = self._registry.uninstall(plugin_id)
        if plugin_id in self._catalog:
            self._catalog[plugin_id].installed = False
        return {"success": success}

    def validate_plugin(self, path: str) -> Dict[str, Any]:
        """Validate a plugin file."""
        from .plugins import PluginManager
        pm = PluginManager()
        return pm.validate_plugin(path)
