from shapely.geometry import (
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from shapely.ops import unary_union

try:
    import alphashape

    HAS_ALPHASHAPE = True
except ImportError:
    HAS_ALPHASHAPE = False


def concave_isochrone_from_subgraph(G, sub, alpha=None):
    """
    Build concave hull (alpha shape) from reachable graph nodes.
    Always returns a Polygon (or None).
    """
    if not HAS_ALPHASHAPE:
        raise RuntimeError(
            "Concave hull mode selected, but `alphashape` is not installed. "
            "Install it with: pip install alphashape"
        )

    pts = [(G.nodes[n]["x"], G.nodes[n]["y"]) for n in sub.nodes()]
    if len(pts) == 0:
        return None

    convex = MultiPoint(pts).convex_hull

    def to_polygon(shape):
        """Normalize arbitrary geometry to a single Polygon."""
        if shape.is_empty:
            return None

        if isinstance(shape, Polygon):
            return shape

        if isinstance(shape, MultiPolygon):
            largest = max(shape.geoms, key=lambda g: g.area)
            return largest

        if isinstance(shape, (Point, MultiPoint, LineString, MultiLineString)):
            ch = MultiPoint(pts).convex_hull
            if isinstance(ch, Polygon):
                return ch
            return ch.buffer(1.0)

        ch = shape.convex_hull
        if isinstance(ch, Polygon):
            return ch
        return ch.buffer(1.0)

    if len(pts) < 4:
        hull = convex
    else:
        alpha_value = alpha
        if alpha_value is None:
            try:
                alpha_value = alphashape.optimizealpha(pts)
            except Exception:
                alpha_value = None

        if not alpha_value or alpha_value <= 0:
            hull = convex
        else:
            hull = alphashape.alphashape(pts, alpha_value)
            if hull.is_empty:
                hull = convex

    poly = to_polygon(hull)
    if poly is None:
        return None

    # If the concave hull collapses to a tiny patch compared to the convex hull,
    # fall back to the convex hull to avoid unrealistic "5 m wide" isochrones.
    convex_area = convex.area if hasattr(convex, "area") else 0.0
    if convex_area > 0 and poly.area < 0.05 * convex_area:
        return to_polygon(convex)

    return poly


def buffer_isochrone_from_segments(segs, edge_width_m, smooth_m):
    """
    Existing buffer-based isochrone: union of segments -> buffer -> smooth.
    Returns a single Polygon (largest patch).
    """
    if not segs:
        return None

    lines = unary_union(segs)
    area = lines.buffer(edge_width_m)

    smooth = area.buffer(smooth_m).buffer(-smooth_m)
    if smooth.is_empty:
        return None

    if smooth.geom_type == "Polygon":
        return Polygon(smooth.exterior)

    if smooth.geom_type == "MultiPolygon":
        largest = max(smooth.geoms, key=lambda g: g.area)
        return Polygon(largest.exterior)

    polys = [g for g in getattr(smooth, "geoms", []) if g.geom_type == "Polygon"]
    if not polys:
        return None
    largest = max(polys, key=lambda g: g.area)
    return Polygon(largest.exterior)
