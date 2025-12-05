import networkx as nx
import numpy as np
import streamlit as st
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString


def build_graph_from_roads(roads_gdf):
    """
    Build undirected graph & KD-tree from road geometries.
    Adds a progress bar over road geometries.
    """
    st.write("Building graph from road geometries...")
    total = len(roads_gdf)
    progress = st.progress(0.0)
    status = st.empty()

    G = nx.Graph()

    for idx, geom in enumerate(roads_gdf.geometry):
        if geom is None:
            progress.progress((idx + 1) / total)
            continue

        lines = geom.geoms if isinstance(geom, MultiLineString) else [geom]

        for ls in lines:
            coords = list(ls.coords)
            for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
                u = (x0, y0)
                v = (x1, y1)

                if u not in G:
                    G.add_node(u, x=x0, y=y0)
                if v not in G:
                    G.add_node(v, x=x1, y=y1)

                G.add_edge(u, v, length=LineString([u, v]).length)

        progress.progress((idx + 1) / total)
        if (idx + 1) % 1000 == 0 or idx == total - 1:
            status.text(f"Processed {idx + 1}/{total} road geometries")

    status.text("Graph building complete.")
    st.write(f"Graph built: {len(G.nodes)} nodes, {len(G.edges)} edges.")

    st.write("Building KD-tree for nearest-node search...")
    valid_nodes = [n for n in G.nodes if G.degree(n) > 0]
    node_keys = valid_nodes
    node_xy = np.array([(G.nodes[n]["x"], G.nodes[n]["y"]) for n in node_keys], float)

    kdtree = cKDTree(node_xy)
    st.write("KD-tree ready.")

    return G, kdtree, node_keys
