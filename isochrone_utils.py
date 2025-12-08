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
    quiet=True,
    log_every=50,
    warn_buffer_size=10,
):
    """
    Compute isochrone polygons for a single distance for all points, with progress bar.
    boundary_mode: "buffer" (default) or "concave"
    alpha_value: float or None (for concave mode)
    quiet: when True, reduce Streamlit chatter and batch progress updates
    log_every: how many points between progress/warning flushes
    warn_buffer_size: max warnings to show per flush
    """

    def nearest_node_id(x, y):
        dist, idx = kdtree.query([x, y], k=1)
        if dist > max_snap_dist:
            raise ValueError(
                "Point (%.1f, %.1f) is %.1f m from nearest node (> %.1f m)"
                % (x, y, dist, max_snap_dist)
            )
        return node_keys[int(idx)]

    def make_isochrone_contour(point, idx, warnings):
        try:
            center = nearest_node_id(point.x, point.y)
        except ValueError as e:
            warnings.append(f"[point {idx}] snapping failed: {e}")
            return None

        dists = nx.single_source_dijkstra_path_length(
            G, center, cutoff=iso_dist_m, weight="length"
        )
        if not dists:
            warnings.append(f"[point {idx}] no reachable nodes")
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

    if not quiet:
        st.write(
            f"Computing isochrones for distance {iso_dist_m} m "
            f"using boundary mode '{boundary_mode}'..."
        )
    contours = []
    total = len(points_gdf)
    progress = None if quiet else st.progress(0.0)
    status = None if quiet else st.empty()
    warnings = []

    def flush_warnings():
        if quiet or not warnings:
            return
        msg = "\n".join(warnings[:warn_buffer_size])
        st.info(msg)
        warnings.clear()

    for i, pt in enumerate(points_gdf.geometry):
        contour = make_isochrone_contour(pt, i, warnings)
        contours.append(contour)
        if (i + 1) % log_every == 0 or i == total - 1:
            frac = float(i + 1) / float(total)
            if progress is not None:
                progress.progress(frac)
            if status is not None:
                status.text(
                    f"Distance {iso_dist_m} m: processed {i + 1}/{total} points "
                    f"({int(frac * 100)}%)"
                )
            flush_warnings()

    flush_warnings()

    if status is not None:
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
    quiet=True,
    log_every=50,
    warn_buffer_size=10,
):
    """
    Compute isochrones for multiple distance bands with outer progress bar.
    Optimized to run Dijkstra once per point (at max distance) and reuse results
    for larger distance bands instead of restarting each time.
    """
    distances_sorted = sorted(set(distances_m))

    # Single distance: use existing path for clarity
    if len(distances_sorted) == 1:
        return compute_isochrones_for_distance(
            G=G,
            kdtree=kdtree,
            node_keys=node_keys,
            points_gdf=points_gdf,
            iso_dist_m=distances_sorted[0],
            edge_width_m=edge_width_m,
            smooth_m=smooth_m,
            max_snap_dist=max_snap_dist,
            crs_metric=crs_metric,
            boundary_mode=boundary_mode,
            alpha_value=alpha_value,
            quiet=quiet,
            log_every=log_every,
            warn_buffer_size=warn_buffer_size,
        )

    all_results = []

    total_d = len(distances_sorted)
    if not quiet:
        st.write("Computing isochrones for all distance bands...")
    outer_progress = None if quiet else st.progress(0.0)
    outer_status = None if quiet else st.empty()
    iso_progress = None if quiet else st.progress(0.0)

    total_points = len(points_gdf)
    per_point_progress = None if quiet else st.progress(0.0)
    per_point_status = None if quiet else st.empty()
    warnings = []

    def flush_warnings():
        if quiet or not warnings:
            return
        msg = "\n".join(warnings[:warn_buffer_size])
        st.info(msg)
        warnings.clear()

    contours_by_dist = {d: [] for d in distances_sorted}

    def nearest_node_id(x, y):
        dist, idx = kdtree.query([x, y], k=1)
        if dist > max_snap_dist:
            raise ValueError(
                "Point (%.1f, %.1f) is %.1f m from nearest node (> %.1f m)"
                % (x, y, dist, max_snap_dist)
            )
        return node_keys[int(idx)]

    max_dist = max(distances_sorted)
    iso_completed = 0
    total_iso = max(1, total_points * total_d)

    for i, pt in enumerate(points_gdf.geometry):
        try:
            center = nearest_node_id(pt.x, pt.y)
        except ValueError as e:
            warnings.append(f"[point {i}] snapping failed: {e}")
            for d in distances_sorted:
                contours_by_dist[d].append(None)
                iso_completed += 1
                if iso_progress is not None:
                    iso_progress.progress(iso_completed / total_iso)
            continue

        dists = nx.single_source_dijkstra_path_length(
            G, center, cutoff=max_dist, weight="length"
        )
        if not dists:
            warnings.append(f"[point {i}] no reachable nodes within {max_dist} m")
            for d in distances_sorted:
                contours_by_dist[d].append(None)
                iso_completed += 1
                if iso_progress is not None:
                    iso_progress.progress(iso_completed / total_iso)
            continue

        for d in distances_sorted:
            nodes_within = [n for n, dist in dists.items() if dist <= d]
            if not nodes_within:
                contours_by_dist[d].append(None)
                iso_completed += 1
                if iso_progress is not None:
                    iso_progress.progress(iso_completed / total_iso)
                continue

            sub = G.subgraph(nodes_within)

            if boundary_mode == "concave":
                try:
                    contour = concave_isochrone_from_subgraph(G, sub, alpha=alpha_value)
                except RuntimeError as e:
                    st.error(str(e))
                    contour = None
            else:
                segs = [
                    LineString(
                        [(G.nodes[u]["x"], G.nodes[u]["y"]), (G.nodes[v]["x"], G.nodes[v]["y"])]
                    )
                    for u, v in sub.edges()
                ]
                contour = buffer_isochrone_from_segments(segs, edge_width_m, smooth_m)

            contours_by_dist[d].append(contour)
            iso_completed += 1
            if iso_progress is not None:
                iso_progress.progress(iso_completed / total_iso)

        if (i + 1) % log_every == 0 or i == total_points - 1:
            frac = float(i + 1) / float(total_points)
            if per_point_progress is not None:
                per_point_progress.progress(frac)
            if per_point_status is not None:
                per_point_status.text(
                    f"Processed {i + 1}/{total_points} points across {total_d} distance bands "
                    f"({int(frac * 100)}%)"
                )
            flush_warnings()

    flush_warnings()

    if per_point_status is not None:
        per_point_status.text("All points processed for all distance bands.")
    if iso_progress is not None:
        iso_progress.progress(1.0)

    base_df = pd.DataFrame(points_gdf).drop(
        columns=[points_gdf.geometry.name], errors="ignore"
    )

    for d in distances_sorted:
        iso_gdf = gpd.GeoDataFrame(
            base_df.copy(),
            geometry=contours_by_dist[d],
            crs=crs_metric,
        )
        iso_gdf = iso_gdf[iso_gdf.geometry.notnull() & ~iso_gdf.geometry.is_empty]
        iso_gdf["dist_m"] = d
        if len(iso_gdf) > 0:
            all_results.append(iso_gdf)
        if outer_progress is not None:
            outer_progress.progress(float(distances_sorted.index(d) + 1) / float(total_d))

    if outer_status is not None:
        outer_status.text("All distance bands completed.")

    if not all_results:
        base_cols = list(points_gdf.columns)
        empty_df = pd.DataFrame(columns=base_cols + ["dist_m"])
        geom_col = points_gdf.geometry.name if hasattr(points_gdf, "geometry") else "geometry"
        empty_gdf = gpd.GeoDataFrame(empty_df, geometry=geom_col, crs=crs_metric)
        return empty_gdf

    return gpd.GeoDataFrame(pd.concat(all_results, ignore_index=True), crs=crs_metric)
