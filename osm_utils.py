import osmnx as ox
import streamlit as st


def load_osm_roads(regions, crs_metric, network_type):
    """Load OSM road network for given regions."""
    st.write(f"Downloading OSM roads for regions: {regions}")
    with st.spinner("Downloading graph from OSM. It may take a while..."):
        G_osm = ox.graph_from_place(regions, network_type=network_type)

    st.write("Projecting OSM graph to metric CRS...")
    G_osm = ox.project_graph(G_osm, to_crs=crs_metric)

    st.write("Extracting edges as GeoDataFrame...")
    edges = ox.graph_to_gdfs(G_osm, nodes=False, edges=True)
    edges = edges[edges.geometry.notnull()]
    edges = edges[edges.geometry.geom_type.isin(["LineString", "MultiLineString"])]
    st.write(f"Downloaded {len(edges)} road segments from OSM.")
    return edges
