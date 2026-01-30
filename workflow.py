import streamlit as st

from izochrones_ui.boundary_utils import HAS_ALPHASHAPE
from izochrones_ui.i18n import t
from izochrones_ui.isochrone_utils import compute_multi_distance_isochrones
from izochrones_ui.network_utils import build_graph_from_roads
from izochrones_ui.osm_utils import load_osm_roads_around_points


def ensure_roads_and_graph(road_source, distances_m, network_type, crs_metric_default):
    """
    Make sure roads_gdf and graph_data exist in session_state.
    Downloads OSM data when requested.
    """
    if st.session_state.get("roads_gdf") is not None and st.session_state.get("graph_data") is not None:
        return True

    if road_source != "osm":
        st.error(t("error_provide_roads"))
        return False

    try:
        max_dist = max(distances_m) if distances_m else 1000
        pts_wgs = st.session_state["points_gdf"].to_crs("EPSG:4326")
        edges = load_osm_roads_around_points(
            pts_wgs,
            crs_metric=st.session_state.get("crs_metric", crs_metric_default),
            network_type=network_type,
            radius_m=max_dist + 10,
            extra_buffer_m=0,
        )
        st.session_state["roads_gdf"] = edges
        st.session_state["crs_metric"] = st.session_state.get("crs_metric", crs_metric_default)
        roads_metric = edges.to_crs(st.session_state["crs_metric"])
        G, kdtree, node_keys = build_graph_from_roads(roads_metric)
        st.session_state["graph_data"] = {
            "G": G,
            "kdtree": kdtree,
            "node_keys": node_keys,
            "crs": st.session_state["crs_metric"],
            "nodes": len(G.nodes),
            "edges": len(G.edges),
        }
        st.success(
            t("roads_loaded_success") + f" Graph built ({len(G.nodes)} nodes, {len(G.edges)} edges)."
        )
        return True
    except Exception as e:
        st.error(t("error_downloading_roads", e=e))
        return False


def run_isochrone_computation(
    road_source,
    network_type,
    params,
    distances_m,
    crs_metric_default,
):
    """
    Validate inputs and compute isochrones. Mutates session_state.
    """
    if st.session_state.get("points_gdf") is None:
        st.error(t("error_upload_points"))
        return False

    if not distances_m:
        st.error(t("error_valid_distance"))
        return False

    if params["boundary_mode"] == "concave" and not HAS_ALPHASHAPE:
        st.error(t("error_concave_missing"))
        return False

    if not ensure_roads_and_graph(road_source, distances_m, network_type, crs_metric_default):
        return False

    points_metric = st.session_state["points_gdf"].to_crs(params["crs_metric"])
    gd = st.session_state["graph_data"]

    if gd.get("crs") != params["crs_metric"]:
        st.error(t("crs_mismatch_error", cached=gd.get("crs"), current=params["crs_metric"]))
        return False

    try:
        iso_all = compute_multi_distance_isochrones(
            G=gd["G"],
            kdtree=gd["kdtree"],
            node_keys=gd["node_keys"],
            points_gdf=points_metric,
            distances_m=distances_m,
            edge_width_m=params.get("edge_width_m"),
            smooth_m=params.get("smooth_m"),
            max_snap_dist=params["max_snap_dist"],
            crs_metric=params["crs_metric"],
            boundary_mode=params["boundary_mode"],
            alpha_value=params.get("alpha_value"),
        )
    except Exception as e:
        st.error(t("iso_compute_error", e=e))
        return False

    if len(iso_all) == 0:
        st.warning(t("no_iso_warning"))
        return False

    st.session_state["iso_wgs84"] = iso_all.to_crs("EPSG:4326")
    st.success(t("iso_success", n=len(st.session_state["iso_wgs84"])))
    return True
