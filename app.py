from pathlib import Path
import sys

import streamlit as st

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from izochrones_ui.i18n import t
from izochrones_ui.io_utils import gdf_to_geojson_bytes
from izochrones_ui.map_view import build_map_export_html, map_style_for, render_map
from izochrones_ui.state_utils import clear_all, clear_isochrones, init_session_state
from izochrones_ui.ui_styles import inject_styles, inject_toolbar_title, mount_lang_toggle_class
from izochrones_ui.ui_steps import (
    parse_distances_input,
    render_step1_points,
    render_step2_roads,
    render_step3_params,
)
from izochrones_ui.workflow import run_isochrone_computation


def main():
    st.set_page_config(page_title=t("page_title"), layout="wide")
    inject_styles()
    inject_toolbar_title()
    init_session_state()

    left, right = st.columns([1, 2], gap="large")

    with left:
        title_col, lang_col = st.columns([8, 1])
        with title_col:
            st.subheader(t("page_title"))
        with lang_col:
            st.markdown("<div style='height:-2px'></div>", unsafe_allow_html=True)
            lang_symbol = "🇷🇺" if st.session_state.get("lang", "en") == "en" else "🇬🇧"
            lang_help = "Switch to Russian" if st.session_state.get("lang", "en") == "en" else "Переключить на английский"
            if st.button(lang_symbol, key="lang_toggle_btn", help=lang_help):
                st.session_state["lang"] = "ru" if st.session_state.get("lang", "en") == "en" else "en"
            mount_lang_toggle_class()

        render_step1_points(show_title=False)
        st.divider()

        crs_default = st.session_state.get("crs_metric", "EPSG:32637")
        road_source, network_type, crs_metric = render_step2_roads(crs_default, show_title=False)
        st.divider()

        params = render_step3_params(crs_metric)
        st.divider()

        distances_m = parse_distances_input(st.session_state.get("distances_text", ""))
        if st.button(t("compute_btn")):
            run_isochrone_computation(
                road_source=road_source,
                network_type=network_type,
                params=params,
                distances_m=distances_m,
                crs_metric_default=crs_default,
            )

        if st.session_state.get("iso_wgs84") is not None and len(st.session_state["iso_wgs84"]) > 0:
            st.markdown(t("download_results_title"))
            geojson_bytes = gdf_to_geojson_bytes(st.session_state["iso_wgs84"])
            st.download_button(
                label=t("download_button_label"),
                data=geojson_bytes,
                file_name="isochrones_multi_distance.geojson",
                mime="application/geo+json",
            )

    with right:
        st.markdown('<div id="map-sticky-anchor"></div>', unsafe_allow_html=True)
        map_slot = st.empty()

    with right:
        with map_slot.container():
            render_map(
                points_gdf=st.session_state.get("points_gdf"),
                roads_gdf=None,
                iso_wgs84=st.session_state.get("iso_wgs84"),
                zoom=10,
                map_style=map_style_for(st.session_state.get("map_style", "light")),
            )
            style_options = ["light", "dark", "osm"]
            labels = {
                "light": t("map_style_light"),
                "dark": t("map_style_dark"),
                "osm": t("map_style_osm"),
            }
            row_left, row_right = st.columns([3, 2])
            with row_left:
                st.radio(
                    "",
                    options=style_options,
                    format_func=lambda v: labels.get(v, v),
                    horizontal=True,
                    key="map_style",
                    label_visibility="collapsed",
                )
            with row_right:
                with st.container():
                    st.markdown('<div id="clear-actions"></div>', unsafe_allow_html=True)
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button(t("clear_iso_btn"), key="clear_iso_btn_right"):
                            clear_isochrones()
                    with c2:
                        if st.button(t("clear_all_btn"), key="clear_all_btn_right"):
                            clear_all()

            if st.session_state.get("iso_wgs84") is not None and len(st.session_state["iso_wgs84"]) > 0:
                html_out = build_map_export_html(
                    points_gdf=st.session_state.get("points_gdf"),
                    iso_wgs84=st.session_state["iso_wgs84"],
                    map_style_choice=st.session_state.get("map_style", "light"),
                )
                st.download_button(
                    t("map_export_btn"),
                    data=html_out.encode("utf-8"),
                    file_name="isochrones_map.html",
                    mime="text/html",
                )

        # Clear buttons are next to map style selector; removed extra divider below


if __name__ == "__main__":
    main()
