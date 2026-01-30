from pathlib import Path

import pandas as pd
import streamlit as st

from izochrones_ui.display_utils import preview_gdf
from izochrones_ui.i18n import t
from izochrones_ui.io_utils import read_vector_file
from izochrones_ui.network_utils import build_graph_from_roads
from izochrones_ui.points_utils import guess_column_index, points_from_csv


def render_step1_points(show_title: bool = True):
    """Upload / parse points layer."""
    if show_title:
        st.subheader(t("step1_title"))
    points_file = st.file_uploader(
        t("upload_label"),
        type=["geojson", "json", "gpkg", "csv", "xls", "xlsx"],
        key="points_uploader",
        label_visibility="collapsed",
        help=t("upload_help"),
    )

    if points_file is None:
        return

    suffix = Path(points_file.name).suffix.lower()
    try:
        if suffix in [".csv", ".xls", ".xlsx"]:
            df = pd.read_csv(points_file) if suffix == ".csv" else pd.read_excel(points_file)
            if df.empty:
                st.error(t("csv_empty_error"))
                return
            cols = list(df.columns)
            if len(cols) < 2:
                st.error(t("csv_cols_error"))
                return

            lat_guess = guess_column_index(cols, ["lat", "latt", "latitude", "y"])
            lon_guess = guess_column_index(cols, ["lon", "lng", "long", "longitude", "x"])
            lat_default = lat_guess if lat_guess is not None else 0
            lon_default = lon_guess if lon_guess is not None else (1 if len(cols) > 1 else 0)

            with st.popover(t("popover_title")):
                st.caption(t("popover_caption"))
                st.selectbox(t("lat_col_label"), cols, index=lat_default, key="csv_lat_col")
                st.selectbox(t("lon_col_label"), cols, index=lon_default, key="csv_lon_col")
                st.text_input(
                    t("crs_input_label"),
                    value="EPSG:4326",
                    key="csv_crs",
                    help=t("crs_input_help"),
                )

            lat_col = st.session_state.get("csv_lat_col", cols[lat_default])
            lon_col = st.session_state.get("csv_lon_col", cols[lon_default])
            crs_input = st.session_state.get("csv_crs", "EPSG:4326")

            if lat_col == lon_col:
                st.warning(t("lat_lon_same_warning"))
                return

            st.session_state["points_gdf"] = points_from_csv(df, lat_col, lon_col, crs_input)
            st.success(
                t(
                    "csv_loaded_success",
                    n=len(st.session_state["points_gdf"]),
                    lat=lat_col,
                    lon=lon_col,
                    crs=crs_input,
                )
            )
        else:
            st.session_state["points_gdf"] = read_vector_file(points_file)
            st.success(t("point_layer_loaded", n=len(st.session_state["points_gdf"])))
    except Exception as e:
        st.error(t("error_read_point", e=e))

    if st.session_state["points_gdf"] is not None:
        with st.expander(t("preview_points")):
            preview_gdf(st.session_state["points_gdf"], title=t("preview_points"))


def render_step2_roads(crs_metric_default, show_title: bool = True):
    """
    Render road source selection, optional upload, graph build.
    Returns (road_source, network_type, crs_metric_current).
    """
    if show_title:
        st.subheader(t("step2_title"))

    road_options = {"osm": t("road_source_osm"), "upload": t("road_source_upload")}
    road_choice = st.radio(
        t("road_source_label"),
        options=list(road_options.values()),
        horizontal=True,
        label_visibility="collapsed",
    )
    road_source = next(k for k, v in road_options.items() if v == road_choice)

    crs_metric_current = st.session_state.get("crs_metric", crs_metric_default)
    network_type = "all"

    if road_source == "osm":
        st.text_input(
            t("distances_label"),
            value=st.session_state.get("distances_text", "500, 1000"),
            help=t("distances_help"),
            key="distances_text",
        )
        network_type = st.selectbox(t("network_type_label"), options=["all", "drive"], index=0)
    else:
        roads_file = st.file_uploader("", type=["geojson", "json", "gpkg"], key="roads_uploader")
        crs_metric_user = st.session_state.get("crs_metric", crs_metric_current)

        if roads_file is not None:
            try:
                roads_gdf_tmp = read_vector_file(roads_file)
                roads_gdf_tmp = roads_gdf_tmp[roads_gdf_tmp.geometry.geom_type.isin(["LineString", "MultiLineString"])]
                st.session_state["roads_gdf"] = roads_gdf_tmp
                roads_metric = roads_gdf_tmp.to_crs(crs_metric_user)
                G, kdtree, node_keys = build_graph_from_roads(roads_metric)
                st.session_state["graph_data"] = {
                    "G": G,
                    "kdtree": kdtree,
                    "node_keys": node_keys,
                    "crs": crs_metric_user,
                    "nodes": len(G.nodes),
                    "edges": len(G.edges),
                }
                st.success(
                    t("roads_file_loaded", n=len(roads_gdf_tmp))
                    + f" Graph built ({len(G.nodes)} nodes, {len(G.edges)} edges)."
                )
            except Exception as e:
                st.error(t("error_read_roads", e=e))

    if st.session_state.get("graph_data"):
        gd = st.session_state["graph_data"]
        st.caption(t("graph_cached_caption", nodes=gd["nodes"], edges=gd["edges"], crs=gd["crs"]))

    return road_source, network_type, st.session_state.get("crs_metric", crs_metric_current)


def render_step3_params(crs_metric_default):
    """Return user-selected parameters for isochrone computation."""
    with st.expander(t("step3_title"), expanded=False):
        crs_metric = st.text_input(
            t("crs_metric_label"),
            value=st.session_state.get("crs_metric", crs_metric_default),
            key="crs_metric_params",
        )

        max_snap_dist = st.number_input(
            t("max_snap_label"),
            min_value=10.0,
            value=300.0,
            step=10.0,
        )

        boundary_mode = st.selectbox(
            t("boundary_type_label"),
            options=["buffer", "concave"],
            index=0,
            help=t("boundary_help"),
        )

        alpha_value = None
        if boundary_mode == "concave":
            from izochrones_ui.boundary_utils import HAS_ALPHASHAPE

            if not HAS_ALPHASHAPE:
                st.warning(t("concave_warning"))
            alpha_input = st.number_input(t("concave_alpha_label"), min_value=0.0, value=0.0, step=0.1)
            alpha_value = None if alpha_input == 0.0 else float(alpha_input)

        edge_width_m = None
        smooth_m = None
        if boundary_mode == "buffer":
            edge_width_m = st.number_input(t("edge_width_label"), min_value=1.0, value=50.0, step=1.0)
            smooth_m = st.number_input(t("smoothing_label"), min_value=0.0, value=80.0, step=1.0)

    return {
        "max_snap_dist": max_snap_dist,
        "boundary_mode": boundary_mode,
        "alpha_value": alpha_value,
        "edge_width_m": edge_width_m,
        "smooth_m": smooth_m,
        "crs_metric": crs_metric,
    }


def parse_distances_input(distances_text):
    """Parse comma-separated distance string into sorted integers."""
    try:
        return sorted({int(x.strip()) for x in distances_text.split(",") if x.strip()})
    except Exception:
        st.error(t("parse_distance_error"))
        return []
