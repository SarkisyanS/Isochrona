import json
import sys
from pathlib import Path

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
    """Lightweight dark theme polish."""
    st.markdown(
        """
        <style>
        /* Global background and typography */
        @import url('https://fonts.googleapis.com/css2?family=Russo+One&family=Sora:wght@400;600&display=swap');
        .stApp {
            background: radial-gradient(120% 120% at 10% 20%, #0f172a 0%, #0b1020 45%, #050913 100%);
            color: #e2e8f0;
            font-family: "Russo One", "Sora", system-ui, -apple-system, sans-serif;
        }
        body, p, span, label, input, textarea, button, select, option, li, h1, h2, h3, h4, h5 {
            font-family: "Russo One", "Sora", system-ui, -apple-system, sans-serif !important;
            font-weight: 200;
        }
        h1, h2, h3, h4 {
            font-weight: 400;
        }
        /* Keep icon fonts intact (e.g., expanders/arrows) */
        [data-baseweb="icon"], .material-icons {
            font-family: "Material Icons" !important;
            font-weight: 400;
        }
        .block-container {
            padding: 2.5rem 2.5rem 3rem;
            max-width: 900px;
            margin-left: auto;
            margin-right: auto;
        }
        h1, h2, h3, h4 {
            color: #f8fafc;
            letter-spacing: 0.01em;
        }
        /* Cards */
        .step-card {
            background: #101827;
            border: 1px solid #1f2937;
            border-radius: 14px;
            padding: 1.1rem 1.25rem;
            box-shadow: 0 12px 30px rgba(0,0,0,0.25);
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
        .stFileUploader, .stNumberInput, .stTextInput, .stSelectbox, .stRadio, .stTextArea {
            width: 100%;
            max-width: none;
        }
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
        /* Spinner buttons */
        .stNumberInput button[aria-label="Decrease value"] {
            background: #ef4444;
            color: #fff;
            border: none;
        }
        .stNumberInput button[aria-label="Increase value"] {
            background: #22c55e;
            color: #fff;
            border: none;
        }
        .stNumberInput button[aria-label="Decrease value"]:hover {
            filter: brightness(0.95);
        }
        .stNumberInput button[aria-label="Increase value"]:hover {
            filter: brightness(0.95);
        }
        label, .stSelectbox div[data-baseweb="select"] {
            width: auto !important;
        }
        /* Expander */
        details {
            background: #0d1524;
            border-radius: 10px;
            border: 1px solid #1f2937;
        }
        /* Table preview */
        .stDataFrame, .stDataFrame [role="table"] {
            color: #e2e8f0;
        }
        .section-gap {
            margin: 1.6rem 0 1rem;
            border-top: 1px solid #1f2937;
            opacity: 0.75;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="Isochrone Builder", layout="wide")
    inject_styles()
    st.markdown(
        """
        <div style="text-align:center; margin-top: 0.75rem; margin-bottom: 0.75rem;">
            <span style="font-family:'Russo One', sans-serif; font-size:32px; letter-spacing:1px;">ISOCHRONA</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.header("Step 1 – Upload point layer (origins)")

    with st.container():
        points_file = st.file_uploader(
            "Upload point layer",
            type=["geojson", "json", "gpkg"],
            key="points_uploader",
            label_visibility="collapsed",
        )

    points_gdf = None
    if points_file is not None:
        try:
            points_gdf = read_vector_file(points_file)
            st.success(f"Point layer loaded with {len(points_gdf)} features.")
            preview_gdf(points_gdf, title="Points preview")
        except Exception as e:
            st.error(f"Error reading point file: {e}")

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

    st.header("Step 2 – Provide roads")

    road_source = st.radio(
        "Road source",
        options=["Download from OSM", "Upload your own road file"],
        horizontal=True,
        label_visibility="collapsed",
    )

    roads_gdf = None

    if "roads_gdf" not in st.session_state:
        st.session_state["roads_gdf"] = None

    crs_metric_default = "EPSG:32637"

    if road_source == "Download from OSM":
        st.subheader("Download roads from OSM")

        regions_text = st.text_area(
            "Regions (one per line)",
            value="Saint Petersburg, Russia",
            help="Example: 'Moscow Oblast, Russia' or 'Saint Petersburg, Russia'",
        )

        network_type = st.selectbox(
            "OSM network type",
            options=["all", "drive", "walk", "bike"],
            index=0,
        )

        crs_metric_osm = st.text_input(
            "Metric CRS (EPSG code for roads & points)",
            value=crs_metric_default,
        )

        if st.button("Download roads"):
            regions = [r.strip() for r in regions_text.splitlines() if r.strip()]
            if not regions:
                st.error("Please specify at least one region.")
            else:
                try:
                    edges = load_osm_roads(regions, crs_metric_osm, network_type)
                    st.session_state["roads_gdf"] = edges
                    st.session_state["crs_metric"] = crs_metric_osm
                    st.session_state["graph_data"] = None  # invalidate graph cache
                    st.success("OSM roads loaded and stored.")
                    preview_gdf(edges, title="OSM roads preview")
                except Exception as e:
                    st.error(f"Error downloading OSM roads: {e}")

    else:
        st.subheader("Upload your own roads file")

        roads_file = st.file_uploader(
            "",
            type=["geojson", "json", "gpkg"],
            key="roads_uploader",
        )

        crs_metric_user = st.text_input(
            "Metric CRS (EPSG code for roads & points)",
            value=crs_metric_default,
        )

        if roads_file is not None:
            try:
                roads_gdf_tmp = read_vector_file(roads_file)
                roads_gdf_tmp = roads_gdf_tmp[
                    roads_gdf_tmp.geometry.geom_type.isin(
                        ["LineString", "MultiLineString"]
                    )
                ]
                st.session_state["roads_gdf"] = roads_gdf_tmp
                st.session_state["crs_metric"] = crs_metric_user
                st.session_state["graph_data"] = None  # invalidate graph cache
                st.success(
                    f"Road layer loaded with {len(roads_gdf_tmp)} segments and stored."
                )
                preview_gdf(roads_gdf_tmp, title="Roads preview")
            except Exception as e:
                st.error(f"Error reading road file: {e}")

    roads_gdf = st.session_state.get("roads_gdf", None)
    crs_metric = st.session_state.get("crs_metric", crs_metric_default)
    graph_data = st.session_state.get("graph_data", None)

    if roads_gdf is not None:
        if st.button("Build graph using current roads"):
            try:
                roads_metric = roads_gdf.to_crs(crs_metric)
                G, kdtree, node_keys = build_graph_from_roads(roads_metric)
                st.session_state["graph_data"] = {
                    "G": G,
                    "kdtree": kdtree,
                    "node_keys": node_keys,
                    "crs": crs_metric,
                    "nodes": len(G.nodes),
                    "edges": len(G.edges),
                }
                st.success(
                    f"Graph built and cached ({len(G.nodes)} nodes, {len(G.edges)} edges)."
                )
                graph_data = st.session_state["graph_data"]
            except Exception as e:
                st.error(f"Error building graph: {e}")

        if graph_data:
            st.caption(
                f"Cached graph: {graph_data.get('nodes', 0)} nodes, "
                f"{graph_data.get('edges', 0)} edges (CRS: {graph_data.get('crs')})"
            )

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

    st.header("Step 3 – Isochrone parameters")

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

    st.write(f"Current metric CRS for computations: `{crs_metric}`")

    boundary_mode = st.selectbox(
        "Isochrone boundary type",
        options=["buffer", "concave"],
        index=0,
        help=(
            "'buffer' – network-buffer-based isochrone "
            "(uses edge width & smoothing). "
            "'concave' – concave hull (alpha shape) of reachable nodes."
        ),
    )

    alpha_value = None
    if boundary_mode == "concave":
        if not HAS_ALPHASHAPE:
            st.warning(
                "Concave hull mode selected, but `alphashape` is not installed. "
                "Install it via: pip install alphashape"
            )
        alpha_input = st.number_input(
            "Concave hull alpha (0 = auto)",
            min_value=0.0,
            value=0.0,
            step=0.1,
            help="Smaller -> more concave (tighter). Larger -> more convex. 0 = automatic.",
        )
        alpha_value = None if alpha_input == 0.0 else float(alpha_input)
    edge_width_m = None
    smooth_m = None
    if boundary_mode == "buffer":
        edge_width_m = st.number_input(
            "Edge width for buffering (m) [buffer mode only]",
            min_value=1.0,
            value=50.0,
            step=1.0,
        )
        smooth_m = st.number_input(
            "Smoothing radius (m) [buffer mode only]",
            min_value=0.0,
            value=80.0,
            step=1.0,
        )

    try:
        distances_m = sorted(
            {int(x.strip()) for x in distances_text.split(",") if x.strip()}
        )
    except Exception:
        distances_m = []
        st.error("Could not parse distances. Please enter integers separated by commas.")

    st.markdown('<div class="section-gap"></div>', unsafe_allow_html=True)

    st.header("Step 4 – Run isochrones")

    if st.button("Compute isochrones"):
        if points_gdf is None:
            st.error("Please upload a point layer in Step 1.")
        elif roads_gdf is None:
            st.error("Please provide roads in Step 2 (OSM or upload).")
        elif graph_data is None:
            st.error("Please build the graph in Step 2 before computing isochrones.")
        elif graph_data.get("crs") != crs_metric:
            st.error(
                f"Cached graph CRS {graph_data.get('crs')} does not match current CRS {crs_metric}. "
                "Rebuild the graph with the current CRS."
            )
        elif not distances_m:
            st.error("Please provide at least one valid distance in Step 3.")
        elif boundary_mode == "concave" and not HAS_ALPHASHAPE:
            st.error(
                "Concave hull mode selected, but `alphashape` is not installed.\n"
                "Install it with: pip install alphashape"
            )
        else:
            try:
                points_metric = points_gdf.to_crs(crs_metric)

                G = graph_data["G"]
                kdtree = graph_data["kdtree"]
                node_keys = graph_data["node_keys"]

                iso_all = compute_multi_distance_isochrones(
                    G=G,
                    kdtree=kdtree,
                    node_keys=node_keys,
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
                    return

                st.success(f"Generated {len(iso_all)} isochrone polygons in total.")

                iso_wgs84 = iso_all.to_crs("EPSG:4326")

                st.subheader("Result preview map (WGS84)")

                geojson_dict = json.loads(iso_wgs84.to_json())

                # Draw larger (farther) isochrones first, then smaller ones on top
                geojson_dict["features"] = sorted(
                    geojson_dict["features"],
                    key=lambda f: f.get("properties", {}).get("dist_m", 0),
                    reverse=True,
                )

                centroids = iso_wgs84.geometry.centroid
                center_lat = centroids.y.mean()
                center_lon = centroids.x.mean()

                unique_dists = sorted(iso_wgs84["dist_m"].unique())
                base_colors = [
                    [0, 0, 255],
                    [0, 255, 0],
                    [255, 165, 0],
                    [255, 0, 0],
                    [128, 0, 128],
                    [0, 255, 255],
                ]
                color_map = {d: base_colors[i % len(base_colors)] for i, d in enumerate(unique_dists)}

                for feature in geojson_dict["features"]:
                    d = feature["properties"].get("dist_m")
                    color = color_map.get(d, [200, 200, 200])
                    feature["properties"]["fill_color"] = color

                layer = pdk.Layer(
                    "GeoJsonLayer",
                    data=geojson_dict,
                    pickable=True,
                    stroked=True,
                    filled=True,
                    extruded=False,
                    get_fill_color="properties.fill_color",
                    get_line_color=[0, 0, 0],
                    get_line_width=1,
                )

                view_state = pdk.ViewState(
                    longitude=center_lon,
                    latitude=center_lat,
                    zoom=10,
                    pitch=0,
                )

                r = pdk.Deck(layers=[layer], initial_view_state=view_state)
                st.pydeck_chart(r)

                st.subheader("Download results")

                geojson_bytes = gdf_to_geojson_bytes(iso_wgs84)

                st.download_button(
                    label="Download isochrones as GeoJSON (WGS84, all distance bands)",
                    data=geojson_bytes,
                    file_name="isochrones_multi_distance.geojson",
                    mime="application/geo+json",
                )

                preview_gdf(iso_wgs84, title="Isochrones (attributes)")

            except Exception as e:
                st.error(f"Error during isochrone computation: {e}")


if __name__ == "__main__":
    main()
