from pathlib import Path

import geopandas as gpd


def read_vector_file(uploaded_file):
    """Read GeoJSON / JSON / GPKG into a GeoDataFrame."""
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix in [".geojson", ".json"]:
        gdf = gpd.read_file(uploaded_file)
    elif suffix == ".gpkg":
        gdf = gpd.read_file(uploaded_file)
    else:
        raise ValueError("Unsupported file format. Please use GeoJSON or GPKG.")
    return gdf


def gdf_to_geojson_bytes(gdf):
    """Convert a GeoDataFrame to GeoJSON bytes (UTF-8)."""
    geojson_str = gdf.to_json()
    return geojson_str.encode("utf-8")
