"""GIS integration — geographic coordinate transforms and GeoJSON support."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from shapely.geometry import Point, Polygon, MultiPolygon
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False


class CoordinateTransform:
    """
    Converts between geographic coordinates (lat/lon) and simulation grid coords.
    
    Uses simple equirectangular projection. For more accuracy, use shapely + pyproj.
    """

    def __init__(self, bounds: Tuple[float, float, float, float],
                 grid_size: Tuple[int, int]):
        """
        Args:
            bounds: (lat_min, lon_min, lat_max, lon_max) geographic bounds
            grid_size: (width, height) of simulation grid
        """
        self.lat_min, self.lon_min, self.lat_max, self.lon_max = bounds
        self.grid_w, self.grid_h = grid_size
        self.lat_range = self.lat_max - self.lat_min
        self.lon_range = self.lon_max - self.lon_min

    def geo_to_grid(self, lat: float, lon: float) -> Tuple[int, int]:
        """Convert lat/lon to grid x,y."""
        x = int((lon - self.lon_min) / self.lon_range * self.grid_w)
        y = int((lat - self.lat_min) / self.lat_range * self.grid_h)
        return (max(0, min(self.grid_w - 1, x)), max(0, min(self.grid_h - 1, y)))

    def grid_to_geo(self, x: int, y: int) -> Tuple[float, float]:
        """Convert grid x,y to lat/lon."""
        lon = self.lon_min + (x / self.grid_w) * self.lon_range
        lat = self.lat_min + (y / self.grid_h) * self.lat_range
        return (lat, lon)

    def geo_to_grid_float(self, lat: float, lon: float) -> Tuple[float, float]:
        """Convert with float precision for interpolation."""
        x = (lon - self.lon_min) / self.lon_range * self.grid_w
        y = (lat - self.lat_min) / self.lat_range * self.grid_h
        return (max(0, min(self.grid_w, x)), max(0, min(self.grid_h, y)))


class GeoFence:
    """
    Geographic fence — detect when agents enter/leave defined zones.
    """

    def __init__(self, fence_id: str, polygon: List[Tuple[float, float]]):
        self.fence_id = fence_id
        self.polygon = polygon
        self._shapely_poly = None
        if HAS_SHAPELY:
            self._shapely_poly = Polygon(polygon)

    def contains(self, lat: float, lon: float) -> bool:
        """Check if a point is inside the fence."""
        if self._shapely_poly:
            return bool(self._shapely_poly.contains(Point(lat, lon)))
        # Ray casting fallback
        return self._point_in_polygon(lat, lon, self.polygon)

    @staticmethod
    def _point_in_polygon(x: float, y: float, polygon: List[Tuple[float, float]]) -> bool:
        """Ray casting algorithm."""
        n = len(polygon)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside

    def intersects(self, lat: float, lon: float, radius: float) -> bool:
        """Check if a circle intersects the fence."""
        if HAS_SHAPELY and self._shapely_poly:
            return bool(self._shapely_poly.intersects(Point(lat, lon).buffer(radius)))
        # Approximate: check if any polygon vertex is within radius
        for px, py in self.polygon:
            dist = ((lat - px) ** 2 + (lon - py) ** 2) ** 0.5
            if dist <= radius:
                return True
        return self.contains(lat, lon)


class GISIntegration:
    """
    Manages geographic data for the simulation.
    Loads GeoJSON, provides coordinate transforms and geofencing.
    """

    def __init__(self, bounds: Optional[Tuple[float, float, float, float]] = None,
                 grid_size: Tuple[int, int] = (50, 50)):
        self.bounds = bounds or (23.6, 90.3, 23.9, 90.5)  # Default: Dhaka area
        self.grid_size = grid_size
        self.transform = CoordinateTransform(self.bounds, grid_size)
        self._geofences: Dict[str, GeoFence] = {}
        self._features: List[Dict[str, Any]] = []

    def load_geojson(self, path: str) -> List[Dict[str, Any]]:
        """Load GeoJSON file and parse features."""
        data = json.loads(Path(path).read_text())
        features = data.get("features", [])
        self._features = features
        
        for i, feature in enumerate(features):
            geom = feature.get("geometry", {})
            props = feature.get("properties", {})
            if geom.get("type") == "Polygon" and geom.get("coordinates"):
                coords = geom["coordinates"][0]
                polygon = [(c[1], c[0]) for c in coords]  # (lat, lon)
                fence_id = props.get("id", props.get("name", f"zone_{i}"))
                self._geofences[fence_id] = GeoFence(fence_id, polygon)
        
        logger.info(f"Loaded {len(features)} features, {len(self._geofences)} geofences")
        return features

    def add_geofence(self, fence_id: str, polygon: List[Tuple[float, float]]) -> None:
        self._geofences[fence_id] = GeoFence(fence_id, polygon)

    def check_geofences(self, lat: float, lon: float) -> List[str]:
        """Return list of fence IDs the point is inside."""
        return [fid for fid, fence in self._geofences.items() if fence.contains(lat, lon)]

    def get_features_in_grid_cell(self, gx: int, gy: int) -> List[Dict[str, Any]]:
        """Get GeoJSON features that overlap with a grid cell."""
        lat, lon = self.transform.grid_to_geo(gx, gy)
        cell_size_lat = self.transform.lat_range / self.grid_h
        cell_size_lon = self.transform.lon_range / self.grid_w
        
        results = []
        for feature in self._features:
            props = feature.get("properties", {})
            name = props.get("name", props.get("id", "unknown"))
            fence = self._geofences.get(name)
            if fence and fence.intersects(lat, lon, max(cell_size_lat, cell_size_lon)):
                results.append(feature)
        return results

    @property
    def feature_count(self) -> int:
        return len(self._features)

    @property
    def fence_count(self) -> int:
        return len(self._geofences)
