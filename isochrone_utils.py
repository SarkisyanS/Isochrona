import pandas as pd
import geopandas as gpd
import networkx as nx
import streamlit as st
from shapely.geometry import LineString

from izochrones_ui.boundary_utils import (
    buffer_isochrone_from_segments,
    concave_isochrone_from_subgraph,
)


def compute_isochrones_for_distance(
    G,
    kdtree,
    node_keys,
    points_gdf,
    iso_dist_m,
    edge_width_m,
    smooth_m,
    max_snap_dist,
    crs_metric,
    boundary_mode="buffer",
    alpha_value=None,
):
    """
    Compute isochrone polygons for a single distance for all points, with progress bar.
    boundary_mode: "buffer" (default) or "concave"
    alpha_value: float or None (for concave mode)
    """

    def nearest_node_id(x, y):
        dist, idx = kdtree.query([x, y], k=1)
        if dist > max_snap_dist:
            raise ValueError(
                "Point (%.1f, %.1f) is %.1f m from nearest node (> %.1f m)"
                % (x, y, dist, max_snap_dist)
            )
        return node_keys[int(idx)]

    def make_isochrone_contour(point, idx):
        try:
            center = nearest_node_id(point.x, point.y)
        except ValueError as e:
            st.write(f"[point {idx}] snapping failed: {e}")
            return None

        dists = nx.single_source_dijkstra_path_length(
            G, center, cutoff=iso_dist_m, weight="length"
        )
        if not dists:
            st.write(f"[point {idx}] no reachable nodes")
            return None

        sub = G.subgraph(dists.keys())

        if boundary_mode == "concave":
            try:
                return concave_isochrone_from_subgraph(G, sub, alpha=alpha_value)
            except RuntimeError as e:
                st.error(str(e))
                return None

        segs = [
            LineString(
                [(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])]
            )
            for u, v in sub.edges()
        ]
        return buffer_isochrone_from_segments(segs, edge_width_m, smooth_m)

    st.write(
        f"Computing isochrones for distance {iso_dist_m} m "
        f"using boundary mode '{boundary_mode}'..."
    )
    contours = []
    total = len(points_gdf)
    progress = st.progress(0.0)
    status = st.empty()

    for i, pt in enumerate(points_gdf.geometry):
        contour = make_isochrone_contour(pt, i)
        contours.append(contour)
        frac = float(i + 1) / float(total)
        progress.progress(frac)
        if (i + 1) % 50 == 0 or i == total - 1:
            status.text(
                f"Distance {iso_dist_m} m: processed {i + 1}/{total} points "
                f"({int(frac * 100)}%)"
            )

    status.text(f"Distance {iso_dist_m} m: finished.")

    geom_col = points_gdf.geometry.name if hasattr(points_gdf, "geometry") else "geometry"
    base_df = pd.DataFrame(points_gdf).drop(columns=[geom_col], errors="ignore")

    iso_gdf = gpd.GeoDataFrame(
        base_df,
        geometry=contours,
        crs=crs_metric,
    )
    iso_gdf = iso_gdf[iso_gdf.geometry.notnull() & ~iso_gdf.geometry.is_empty]

    st.write(
        f"Distance {iso_dist_m} m: {len(iso_gdf)} valid isochrones out of {len(points_gdf)} points."
    )

    iso_gdf["dist_m"] = iso_dist_m
    return iso_gdf


def compute_multi_distance_isochrones(
    G,
    kdtree,
    node_keys,
    points_gdf,
    distances_m,
    edge_width_m,
    smooth_m,
    max_snap_dist,
    crs_metric,
    boundary_mode="buffer",
    alpha_value=None,
):
    """Compute isochrones for multiple distance bands with outer progress bar."""
    all_results = []

    total_d = len(distances_m)
    st.write("Computing isochrones for all distance bands...")
    outer_progress = st.progress(0.0)
    outer_status = st.empty()

    for j, d in enumerate(distances_m):
        outer_status.text(f"Distance band {j + 1}/{total_d}: {d} m")

        iso_d = compute_isochrones_for_distance(
            G=G,
            kdtree=kdtree,
            node_keys=node_keys,
            points_gdf=points_gdf,
            iso_dist_m=d,
            edge_width_m=edge_width_m,
            smooth_m=smooth_m,
            max_snap_dist=max_snap_dist,
            crs_metric=crs_metric,
            boundary_mode=boundary_mode,
            alpha_value=alpha_value,
        )
        if len(iso_d) > 0:
            all_results.append(iso_d)

        outer_progress.progress(float(j + 1) / float(total_d))

    outer_status.text("All distance bands completed.")

    if not all_results:
        base_cols = list(points_gdf.columns)
        empty_df = pd.DataFrame(columns=base_cols + ["dist_m"])
        geom_col = points_gdf.geometry.name if hasattr(points_gdf, "geometry") else "geometry"
        empty_gdf = gpd.GeoDataFrame(empty_df, geometry=geom_col, crs=crs_metric)
        return empty_gdf

    return gpd.GeoDataFrame(pd.concat(all_results, ignore_index=True), crs=crs_metric)
