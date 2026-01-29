import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pydeck as pdk
import streamlit as st

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from izochrones_ui.boundary_utils import HAS_ALPHASHAPE
from izochrones_ui.display_utils import preview_gdf
from izochrones_ui.io_utils import gdf_to_geojson_bytes, read_vector_file
from izochrones_ui.isochrone_utils import compute_multi_distance_isochrones
from izochrones_ui.network_utils import build_graph_from_roads
from izochrones_ui.osm_utils import load_osm_roads


def inject_styles():
    """Dark theme polish + sticky map container on the right."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Russo+One&family=Sora:wght@400;600&display=swap');
        @import url("https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0");

        .stApp {
            background: radial-gradient(120% 120% at 10% 20%, #0f172a 0%, #0b1020 45%, #050913 100%);
            color: #e2e8f0;
            font-family: "Russo One", "Sora", system-ui, -apple-system, sans-serif;
        }

        body, p, label, input, textarea, button, select, option, li, h1, h2, h3, h4, h5 {
            font-family: "Russo One", "Sora", system-ui, -apple-system, sans-serif !important;
            font-weight: 200;
        }

        h1, h2, h3, h4 {
            font-weight: 400;
            color: #f8fafc;
            letter-spacing: 0.01em;
        }

        /* Keep icon fonts intact */
        .material-icons,
        .material-symbols-outlined,
        .material-symbols-rounded,
        .material-symbols-sharp,
        [data-baseweb="icon"] {
            font-family: "Material Symbols Outlined" !important;
            font-weight: 400 !important;
            font-style: normal;
            line-height: 1;
            letter-spacing: normal;
            text-transform: none;
            display: inline-block;
            white-space: nowrap;
            word-wrap: normal;
            direction: ltr;
            -webkit-font-feature-settings: "liga";
            -webkit-font-smoothing: antialiased;
        }

        .block-container {
            padding: 1.25rem 1.25rem 2rem;
            max-width: 100%;
        }

        /* Buttons */
        .stButton>button {
            background: linear-gradient(90deg, #0ea5e9, #7c3aed);
            color: #f8fafc;
            border: none;
            border-radius: 10px;
            padding: 0.55rem 1.05rem;
            font-weight: 600;
            transition: transform 120ms ease, box-shadow 120ms ease;
            width: auto;
            min-width: 170px;
        }
        .stButton>button:hover {
            transform: translateY(-1px);
            box-shadow: 0 12px 30px rgba(14,165,233,0.35);
        }

        /* Inputs */
        .stNumberInput input, .stTextInput input, textarea {
            background: #1f2937;
            color: #e2e8f0;
            border-radius: 10px;
            border: 1px solid #2b3545;
            width: 100%;
        }
        .stSelectbox div[data-baseweb="select"] {
            background: #1f2937;
            border: 1px solid #2b3545;
            border-radius: 10px;
            color: #e2e8f0;
        }
        .stSelectbox div[data-baseweb="popover"], .stSelectbox [data-baseweb="menu"] {
            background: #1f2937;
            border: 1px solid #2b3545;
            color: #e2e8f0;
        }
        .stTextArea textarea {
            background: #1f2937 !important;
            border: 1px solid #2b3545 !important;
            color: #e2e8f0;
        }

        /* Expander */
        details {
            background: #0d1524;
            border-radius: 10px;
            border: 1px solid #1f2937;
        }

        .section-gap {
            margin: 1.2rem 0 1rem;
            border-top: 1px solid #1f2937;
            opacity: 0.75;
        }

        /* Right-hand map column sticks during left scroll */
        .sticky-map-col {
            position: sticky;
            top: 10px;
            align-self: flex-start;
        }
        /* Preserve card styling for the map panel */
        #map-sticky-anchor + div {
            height: calc(100vh - 16px);
            padding: 12px;
            border: 1px solid #1f2937;
            border-radius: 14px;
            background: #0d1524;
            overflow: hidden;
        }

        /* Make pydeck fill wrapper, kill inner scroll */
        #map-sticky-anchor + div div[data-testid="stDeckGlChart"],
        #map-sticky-anchor + div div[data-testid="stDeckGlJsonChart"] {
            height: 100% !important;
            min-height: 100% !important;
            overflow: hidden !important;
        }
        #map-sticky-anchor + div div[data-testid="stDeckGlChart"] > div,
        #map-sticky-anchor + div div[data-testid="stDeckGlJsonChart"] > div {
            height: 100% !important;
        }
        #map-sticky-anchor + div iframe {
            height: 100% !important;
        }

        /* Progress bar */
        div[role="progressbar"] {
            background: #1f2937 !important;
            border-radius: 999px !important;
            overflow: hidden !important;
            border: 1px solid #2b3545 !important;
            height: 8px !important;
        }
        div[role="progressbar"] > div {
            background: linear-gradient(90deg, #0ea5e9, #7c3aed) !important;
            height: 100% !important;
        }
        </style>
        <script>
        // Add sticky class to the column containing the map anchor
        const stickIsoMapColumn = () => {
          const anchor = document.getElementById("map-sticky-anchor");
          if (!anchor) {
            requestAnimationFrame(stickIsoMapColumn);
            return;
          }
          const col = anchor.closest("div[data-testid='column']");
          if (col && !col.classList.contains("sticky-map-col")) {
            col.classList.add("sticky-map-col");
          }
        };
        requestAnimationFrame(stickIsoMapColumn);
        </script>
        """,
        unsafe_allow_html=True,
    )


def inject_toolbar_title():
    """Place ISOCHRONA label into Streamlit toolbar."""
    st.markdown(
        """
        <script>
        const mountIsoToolbarTitle = () => {
          const html = `
            <div id="iso-toolbar-title"
                 style="display:flex;align-items:center;gap:6px;
                        font-family:'Russo One','Sora',sans-serif;
                        font-size:18px; letter-spacing:1px; color:#e2e8f0;">
                ISOCHRONA
            </div>`;
          const target = document.querySelector("div.stAppToolbar.st-emotion-cache-14vh5up") ||
                         document.querySelector("div[data-testid='stToolbar']");
          if (!target) {
            requestAnimationFrame(mountIsoToolbarTitle);
            return;
          }
          if (!document.getElementById("iso-toolbar-title")) {
            const wrap = document.createElement("div");
            wrap.innerHTML = html.trim();
            target.prepend(wrap.firstChild);
          }
        };
        requestAnimationFrame(mountIsoToolbarTitle);
        </script>
        """,
        unsafe_allow_html=True,
    )


def guess_column_index(columns, keywords):
    normalized = [c.strip().lower().replace(" ", "") for c in columns]
    for idx, name in enumerate(normalized):
        for kw in keywords:
            if name == kw or name.endswith(f"_{kw}") or kw in name:
                return idx
    return None


def points_from_csv(df, lat_col, lon_col, crs="EPSG:4326"):
    df_numeric = df.copy()
    df_numeric[lat_col] = pd.to_numeric(df_numeric[lat_col], errors="coerce")
    df_numeric[lon_col] = pd.to_numeric(df_numeric[lon_col], errors="coerce")
    cleaned = df_numeric.dropna(subset=[lat_col, lon_col])
    if cleaned.empty:
        raise ValueError("No rows with valid numeric latitude/longitude values.")
    geometry = gpd.points_from_xy(cleaned[lon_col], cleaned[lat_col])
    return gpd.GeoDataFrame(cleaned, geometry=geometry, crs=crs)


def _gdf_to_geojson_dict(gdf: gpd.GeoDataFrame):
    if gdf is None or len(gdf) == 0:
        return None
    return json.loads(gdf.to_json())


def render_map(points_gdf=None, roads_gdf=None, iso_wgs84=None, zoom=10):
    layers = []

    # Center
    center_lat, center_lon = 59.9386, 30.3141
    for g in [iso_wgs84, points_gdf, roads_gdf]:
        if g is not None and len(g) > 0:
            g_wgs = g.to_crs("EPSG:4326")
            c = g_wgs.geometry.unary_union.centroid
            center_lon, center_lat = float(c.x), float(c.y)
            break

    # Isochrones
    if iso_wgs84 is not None and len(iso_wgs84) > 0:
        gj = _gdf_to_geojson_dict(iso_wgs84)
        if gj and "features" in gj:
            feats = gj["features"]
            feats.sort(key=lambda f: f.get("properties", {}).get("dist_m", 0), reverse=True)
            try:
                dists = sorted({f.get("properties", {}).get("dist_m") for f in feats})
                base_colors = [
                    [0, 0, 255],
                    [0, 255, 0],
                    [255, 165, 0],
                    [255, 0, 0],
                    [128, 0, 128],
                    [0, 255, 255],
                ]
                color_map = {d: base_colors[i % len(base_colors)] for i, d in enumerate(dists)}
                for f in feats:
                    d = f.get("properties", {}).get("dist_m")
                    f.setdefault("properties", {})
                    f["properties"]["fill_color"] = color_map.get(d, [200, 200, 200])
            except Exception:
                pass

        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=gj,
                pickable=True,
                stroked=True,
                filled=True,
                extruded=False,
                get_fill_color="properties.fill_color",
                get_line_color=[0, 0, 0],
                get_line_width=1,
            )
        )

    # Roads (display-only decimation)
    if roads_gdf is not None and len(roads_gdf) > 0:
        roads_wgs = roads_gdf.to_crs("EPSG:4326").copy()
        try:
            roads_wgs["geometry"] = roads_wgs.geometry.simplify(0.0002, preserve_topology=True)
        except Exception:
            pass
        max_roads_show = 8000
        if len(roads_wgs) > max_roads_show:
            roads_wgs = roads_wgs.sample(max_roads_show, random_state=42)

        roads_gj = _gdf_to_geojson_dict(roads_wgs)

        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                data=roads_gj,
                pickable=False,
                stroked=True,
                filled=False,
                get_line_color=[180, 180, 180],
                get_line_width=2,
            )
        )

    # Points (records)
    if points_gdf is not None and len(points_gdf) > 0:
        pts_wgs = points_gdf.to_crs("EPSG:4326").copy()
        pts_wgs["lon"] = pts_wgs.geometry.x.astype(float)
        pts_wgs["lat"] = pts_wgs.geometry.y.astype(float)
        pts_records = pts_wgs[["lon", "lat"]].dropna().to_dict("records")

        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=pts_records,
                get_position=["lon", "lat"],
                get_radius=5,
                radius_units="meters",
                get_fill_color=[0, 170, 255],
                opacity=0.9,
                pickable=True,
            )
        )

    view_state = pdk.ViewState(longitude=center_lon, latitude=center_lat, zoom=zoom, pitch=0)
    deck = pdk.Deck(layers=layers, initial_view_state=view_state)
    st.pydeck_chart(deck, use_container_width=True, height=780)


def main():
    st.set_page_config(page_title="Isochrone Builder", layout="wide")
    inject_styles()
    inject_toolbar_title()

    # Session state init
    st.session_state.setdefault("points_gdf", None)
    st.session_state.setdefault("roads_gdf", None)
    st.session_state.setdefault("iso_wgs84", None)
    st.session_state.setdefault("crs_metric", "EPSG:32637")
    st.session_state.setdefault("graph_data", None)

    left, right = st.columns([1, 2], gap="large")

    # LEFT first (state updates)
    with left:
        st.subheader("Step 1 – Upload point layer")
        points_file = st.file_uploader(
            "Upload point layer",
            type=["geojson", "json", "gpkg", "csv"],
            key="points_uploader",
            label_visibility="collapsed",
            help="Supports GeoJSON/GPKG or CSV with latitude/longitude columns.",
        )

        if points_file is not None:
            suffix = Path(points_file.name).suffix.lower()
            try:
                if suffix == ".csv":
                    df = pd.read_csv(points_file)
                    if df.empty:
                        st.error("CSV appears to be empty.")
                    else:
                        cols = list(df.columns)
                        if len(cols) < 2:
                            st.error("CSV must have at least two columns for latitude and longitude.")
                        else:
                            lat_guess = guess_column_index(cols, ["lat", "latt", "latitude", "y"])
                            lon_guess = guess_column_index(cols, ["lon", "lng", "long", "longitude", "x"])
                            lat_default = lat_guess if lat_guess is not None else 0
                            lon_default = lon_guess if lon_guess is not None else (1 if len(cols) > 1 else 0)

                            with st.popover("Select latitude / longitude columns"):
                                st.caption("Pick which CSV columns contain coordinates.")
                                st.selectbox("Latitude column", cols, index=lat_default, key="csv_lat_col")
                                st.selectbox("Longitude column", cols, index=lon_default, key="csv_lon_col")
                                st.text_input(
                                    "Coordinate CRS (EPSG code)",
                                    value="EPSG:4326",
                                    key="csv_crs",
                                    help="Commonly EPSG:4326 for WGS84 latitude/longitude.",
                                )

                            lat_col = st.session_state.get("csv_lat_col", cols[lat_default])
                            lon_col = st.session_state.get("csv_lon_col", cols[lon_default])
                            crs_input = st.session_state.get("csv_crs", "EPSG:4326")

                            if lat_col == lon_col:
                                st.warning("Latitude and longitude columns must be different.")
                            else:
                                st.session_state["points_gdf"] = points_from_csv(df, lat_col, lon_col, crs_input)
                                st.success(
                                    f"Loaded {len(st.session_state['points_gdf'])} points "
                                    f"(lat='{lat_col}', lon='{lon_col}', CRS={crs_input})."
                                )
                else:
                    st.session_state["points_gdf"] = read_vector_file(points_file)
                    st.success(f"Point layer loaded: {len(st.session_state['points_gdf'])} features.")
            except Exception as e:
                st.error(f"Error reading point file: {e}")

        if st.session_state["points_gdf"] is not None:
            with st.expander("Points preview"):
                preview_gdf(st.session_state["points_gdf"], title="Points preview")

        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

        st.subheader("Step 2 – Provide roads")

        road_source = st.radio(
            "Road source",
            options=["Download from OSM", "Upload your own road file"],
            horizontal=True,
            label_visibility="collapsed",
        )

        crs_metric_default = st.session_state.get("crs_metric", "EPSG:32637")

        if road_source == "Download from OSM":
            regions_text = st.text_area(
                "Regions (one per line)",
                value="Saint Petersburg, Russia",
                help="Example: 'Moscow Oblast, Russia' or 'Saint Petersburg, Russia'",
            )
            network_type = st.selectbox("OSM network type", options=["all", "drive", "walk", "bike"], index=0)
            crs_metric_osm = st.text_input("Metric CRS (EPSG code for roads & points)", value=crs_metric_default)

            if st.button("Download roads"):
                regions = [r.strip() for r in regions_text.splitlines() if r.strip()]
                if not regions:
                    st.error("Please specify at least one region.")
                else:
                    try:
                        edges = load_osm_roads(regions, crs_metric_osm, network_type)
                        st.session_state["roads_gdf"] = edges
                        st.session_state["crs_metric"] = crs_metric_osm
                        st.session_state["graph_data"] = None
                        st.success("OSM roads loaded.")
                    except Exception as e:
                        st.error(f"Error downloading OSM roads: {e}")

        else:
            roads_file = st.file_uploader("", type=["geojson", "json", "gpkg"], key="roads_uploader")
            crs_metric_user = st.text_input("Metric CRS (EPSG code for roads & points)", value=crs_metric_default)

            if roads_file is not None:
                try:
                    roads_gdf_tmp = read_vector_file(roads_file)
                    roads_gdf_tmp = roads_gdf_tmp[
                        roads_gdf_tmp.geometry.geom_type.isin(["LineString", "MultiLineString"])
                    ]
                    st.session_state["roads_gdf"] = roads_gdf_tmp
                    st.session_state["crs_metric"] = crs_metric_user
                    st.session_state["graph_data"] = None
                    st.success(f"Road layer loaded: {len(roads_gdf_tmp)} segments.")
                except Exception as e:
                    st.error(f"Error reading road file: {e}")

        if st.session_state["roads_gdf"] is not None:
            if st.button("Build graph using current roads"):
                try:
                    crs_metric = st.session_state["crs_metric"]
                    roads_metric = st.session_state["roads_gdf"].to_crs(crs_metric)
                    G, kdtree, node_keys = build_graph_from_roads(roads_metric)
                    st.session_state["graph_data"] = {
                        "G": G,
                        "kdtree": kdtree,
                        "node_keys": node_keys,
                        "crs": crs_metric,
                        "nodes": len(G.nodes),
                        "edges": len(G.edges),
                    }
                    st.success(f"Graph built ({len(G.nodes)} nodes, {len(G.edges)} edges).")
                except Exception as e:
                    st.error(f"Error building graph: {e}")

            if st.session_state["graph_data"]:
                gd = st.session_state["graph_data"]
                st.caption(f"Cached graph: {gd['nodes']} nodes, {gd['edges']} edges (CRS: {gd['crs']})")

            with st.expander("Roads preview"):
                preview_gdf(st.session_state["roads_gdf"], title="Roads preview")

        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

        st.subheader("Step 3 – Isochrone parameters")

        distances_text = st.text_input(
            "Isochrone distances (m, comma-separated)",
            value="500, 1000",
            help="Example: 500, 700, 1500",
        )

        max_snap_dist = st.number_input(
            "Max snap distance to nearest road (m)",
            min_value=10.0,
            value=300.0,
            step=10.0,
        )

        crs_metric = st.session_state.get("crs_metric", crs_metric_default)
        st.write(f"Current metric CRS: `{crs_metric}`")

        boundary_mode = st.selectbox(
            "Isochrone boundary type",
            options=["buffer", "concave"],
            index=0,
            help="'buffer' – network-buffer-based isochrone. 'concave' – concave hull.",
        )

        alpha_value = None
        if boundary_mode == "concave":
            if not HAS_ALPHASHAPE:
                st.warning("Concave hull selected, but `alphashape` is not installed (pip install alphashape).")
            alpha_input = st.number_input("Concave hull alpha (0 = auto)", min_value=0.0, value=0.0, step=0.1)
            alpha_value = None if alpha_input == 0.0 else float(alpha_input)

        edge_width_m = None
        smooth_m = None
        if boundary_mode == "buffer":
            edge_width_m = st.number_input("Edge width for buffering (m)", min_value=1.0, value=50.0, step=1.0)
            smooth_m = st.number_input("Smoothing radius (m)", min_value=0.0, value=80.0, step=1.0)

        try:
            distances_m = sorted({int(x.strip()) for x in distances_text.split(",") if x.strip()})
        except Exception:
            distances_m = []
            st.error("Could not parse distances. Please enter integers separated by commas.")

        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

        st.subheader("Step 4 – Run isochrones")

        if st.button("Compute isochrones"):
            if st.session_state["points_gdf"] is None:
                st.error("Please upload a point layer in Step 1.")
            elif st.session_state["roads_gdf"] is None:
                st.error("Please provide roads in Step 2.")
            elif st.session_state["graph_data"] is None:
                st.error("Please build the graph in Step 2 before computing isochrones.")
            elif not distances_m:
                st.error("Please provide at least one valid distance.")
            elif boundary_mode == "concave" and not HAS_ALPHASHAPE:
                st.error("Concave hull selected, but `alphashape` is not installed.")
            else:
                try:
                    points_metric = st.session_state["points_gdf"].to_crs(crs_metric)
                    gd = st.session_state["graph_data"]

                    if gd.get("crs") != crs_metric:
                        st.error(f"Cached graph CRS {gd.get('crs')} != current CRS {crs_metric}. Rebuild graph.")
                    else:
                        iso_all = compute_multi_distance_isochrones(
                            G=gd["G"],
                            kdtree=gd["kdtree"],
                            node_keys=gd["node_keys"],
                            points_gdf=points_metric,
                            distances_m=distances_m,
                            edge_width_m=edge_width_m,
                            smooth_m=smooth_m,
                            max_snap_dist=max_snap_dist,
                            crs_metric=crs_metric,
                            boundary_mode=boundary_mode,
                            alpha_value=alpha_value,
                        )

                        if len(iso_all) == 0:
                            st.warning("No valid isochrones generated.")
                        else:
                            st.session_state["iso_wgs84"] = iso_all.to_crs("EPSG:4326")
                            st.success(f"Generated {len(st.session_state['iso_wgs84'])} isochrone polygons.")
                except Exception as e:
                    st.error(f"Error during isochrone computation: {e}")

        if st.session_state["iso_wgs84"] is not None and len(st.session_state["iso_wgs84"]) > 0:
            st.markdown("**Download results**")
            geojson_bytes = gdf_to_geojson_bytes(st.session_state["iso_wgs84"])
            st.download_button(
                label="Download isochrones as GeoJSON (WGS84, all distance bands)",
                data=geojson_bytes,
                file_name="isochrones_multi_distance.geojson",
                mime="application/geo+json",
            )
            with st.expander("Isochrones preview"):
                preview_gdf(st.session_state["iso_wgs84"], title="Isochrones (attributes)")

        st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)
        a, b = st.columns(2)
        if a.button("Clear isochrones"):
            st.session_state["iso_wgs84"] = None
        if b.button("Clear all"):
            st.session_state["points_gdf"] = None
            st.session_state["roads_gdf"] = None
            st.session_state["iso_wgs84"] = None
            st.session_state["graph_data"] = None

    # RIGHT: anchor + empty right after it becomes sticky via CSS (#map-sticky-anchor + div)
    with right:
        st.markdown('<div id="map-sticky-anchor"></div>', unsafe_allow_html=True)
        map_slot = st.empty()

    # Render map into the sticky slot AFTER left updated state
    with right:
        with map_slot.container():
            render_map(
                points_gdf=st.session_state["points_gdf"],
                roads_gdf=st.session_state["roads_gdf"],
                iso_wgs84=st.session_state["iso_wgs84"],
                zoom=10,
            )


if __name__ == "__main__":
    main()
