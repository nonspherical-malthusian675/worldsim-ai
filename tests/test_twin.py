"""Tests for digital twin, GIS, plugins, marketplace."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worldsim.twin.gis import CoordinateTransform, GeoFence, GISIntegration
from worldsim.twin.plugins import PluginManager, Plugin, PluginHook, LoggingPlugin, MetricsExportPlugin
from worldsim.twin.marketplace import MarketplaceAPI, PluginRegistry, PluginMetadata
from worldsim.twin.connector import TwinConnector, APIKeyAuth, RateLimiter
from worldsim.twin.core import DigitalTwin, SyncMode
import tempfile, json

def test_coordinate_transform():
    ct = CoordinateTransform(bounds=(23.6, 90.3, 23.9, 90.5), grid_size=(50, 50))
    x, y = ct.geo_to_grid(23.75, 90.4)
    assert 0 <= x < 50 and 0 <= y < 50
    lat, lon = ct.grid_to_geo(25, 25)
    assert 23.6 <= lat <= 23.9 and 90.3 <= lon <= 90.5
    # Round-trip
    x2, y2 = ct.geo_to_grid(lat, lon)
    assert abs(x2 - 25) <= 1 and abs(y2 - 25) <= 1
    print("✓ CoordinateTransform")

def test_geofence():
    # Simple square fence
    fence = GeoFence("test", [(0, 0), (0, 10), (10, 10), (10, 0)])
    assert fence.contains(5, 5)
    assert not fence.contains(15, 5)
    assert not fence.contains(-1, 5)
    print("✓ GeoFence")

def test_plugin_manager():
    pm = PluginManager()
    assert len(pm.list_plugins()) == 0
    # Test built-in plugins
    lp = LoggingPlugin()
    pm._plugins["logging"] = lp
    pm.register_hook("logging", PluginHook.TICK_END)
    results = pm.execute_hook(PluginHook.TICK_END, {"tick": 1})
    assert len(results) >= 0  # no crash
    print("✓ PluginManager")

def test_metrics_export_plugin():
    mep = MetricsExportPlugin()
    mep.execute(PluginHook.TICK_END, {"metrics": {"efficiency": 0.85, "throughput": 4.2}})
    mep.execute(PluginHook.TICK_END, {"metrics": {"efficiency": 0.87, "throughput": 4.5}})
    output = mep.get_prometheus_output()
    assert "efficiency" in output
    assert "throughput" in output
    print("✓ MetricsExportPlugin")

def test_marketplace():
    import tempfile, shutil
    tmp = tempfile.mkdtemp()
    try:
        registry = PluginRegistry(registry_dir=tmp)
        mp = MarketplaceAPI(registry=registry)
        plugins = mp.list_available()
        assert len(plugins) > 0
        results = mp.search("logging")
        assert len(results) > 0
        install = mp.install_plugin("logging")
        assert install["success"]
        installed = registry.get_installed()
        assert len(installed) > 0
        uninstall = mp.uninstall_plugin("logging")
        assert uninstall["success"]
        print("✓ MarketplaceAPI")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def test_twin_connector():
    tc = TwinConnector("test_twin")
    keys = tc.get_api_keys()
    assert len(keys) >= 2
    new_key = tc.generate_api_key("test_user", "write")
    assert len(new_key) == 32
    assert tc.authenticate(new_key, "write")
    assert tc.check_rate_limit("client1")
    result = tc.push_state("sensor_1", {"temp": 25.5})
    assert result["success"]
    state = tc.pull_state()
    assert state["success"]
    assert state["external_sources"] == ["sensor_1"]
    stats = tc.get_stats()
    assert stats["twin_id"] == "test_twin"
    print("✓ TwinConnector")

def test_rate_limiter():
    rl = RateLimiter(max_requests=3, window_seconds=1)
    assert rl.check("c1")
    assert rl.check("c1")
    assert rl.check("c1")
    assert not rl.check("c1")  # rate limited
    print("✓ RateLimiter")

def test_digital_twin():
    dt = DigitalTwin(twin_id="test_dt")
    assert dt.twin_id == "test_dt"
    assert dt.sync_mode == SyncMode.REPLAY
    dt.sync_mode = SyncMode.LIVE
    assert dt.sync_mode == SyncMode.LIVE
    info = dt.get_info()
    assert info["twin_id"] == "test_dt"
    print("✓ DigitalTwin")

if __name__ == "__main__":
    test_coordinate_transform()
    test_geofence()
    test_plugin_manager()
    test_metrics_export_plugin()
    test_marketplace()
    test_twin_connector()
    test_rate_limiter()
    test_digital_twin()
    print("\n✅ All digital twin tests passed!")
