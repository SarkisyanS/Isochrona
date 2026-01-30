import streamlit as st


def init_session_state():
    """Ensure default session values exist."""
    st.session_state.setdefault("lang", "en")
    st.session_state.setdefault("points_gdf", None)
    st.session_state.setdefault("roads_gdf", None)
    st.session_state.setdefault("iso_wgs84", None)
    st.session_state.setdefault("crs_metric", "EPSG:32637")
    st.session_state.setdefault("graph_data", None)
    st.session_state.setdefault("map_style", "light")


def clear_isochrones():
    st.session_state["iso_wgs84"] = None


def clear_all():
    st.session_state["points_gdf"] = None
    st.session_state["roads_gdf"] = None
    st.session_state["iso_wgs84"] = None
    st.session_state["graph_data"] = None
