import osmnx as ox
import pandas as pd
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


def load_osm_roads_around_points(points_wgs84, crs_metric, network_type, radius_m, extra_buffer_m=500):
    """
    Download OSM roads around each point within (radius_m + extra_buffer_m).
    Points must be in WGS84.
    """
    if points_wgs84 is None or len(points_wgs84) == 0:
        raise ValueError("Points GeoDataFrame is empty.")

    dist = float(radius_m) + float(extra_buffer_m)
    edges_list = []

    for pt in points_wgs84.geometry:
        center = (pt.y, pt.x)
        with st.spinner(f"Downloading roads. It make take a while..."):
            G_osm = ox.graph_from_point(center_point=center, dist=dist, network_type=network_type, simplify=True)
            G_proj = ox.project_graph(G_osm, to_crs=crs_metric)
            edges = ox.graph_to_gdfs(G_proj, nodes=False, edges=True)
            edges = edges[edges.geometry.notnull()]
            edges = edges[edges.geometry.geom_type.isin(["LineString", "MultiLineString"])]
            edges_list.append(edges)

    if not edges_list:
        return pd.DataFrame(columns=["geometry"])

    edges_all = pd.concat(edges_list, ignore_index=True)
    edges_all["geom_wkb"] = edges_all.geometry.apply(lambda g: g.wkb)
    edges_all = edges_all.drop_duplicates(subset=["geom_wkb"]).drop(columns=["geom_wkb"])
    st.write(f"Downloaded {len(edges_all)} unique road segments from OSM.")
    return edges_all
