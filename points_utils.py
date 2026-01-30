import geopandas as gpd
import pandas as pd


def guess_column_index(columns, keywords):
    normalized = [c.strip().lower().replace(" ", "") for c in columns]
    for idx, name in enumerate(normalized):
        for kw in keywords:
            if name == kw or name.endswith(f"_{kw}") or kw in name:
                return idx
    return None


def points_from_csv(df, lat_col, lon_col, crs="EPSG:4326"):
    """
    Convert a CSV/Excel dataframe with lat/lon columns into GeoDataFrame.
    Non-numeric rows are dropped.
    """
    df_numeric = df.copy()
    df_numeric[lat_col] = pd.to_numeric(df_numeric[lat_col], errors="coerce")
    df_numeric[lon_col] = pd.to_numeric(df_numeric[lon_col], errors="coerce")
    cleaned = df_numeric.dropna(subset=[lat_col, lon_col])
    if cleaned.empty:
        raise ValueError("No rows with valid numeric latitude/longitude values.")
    geometry = gpd.points_from_xy(cleaned[lon_col], cleaned[lat_col])
    return gpd.GeoDataFrame(cleaned, geometry=geometry, crs=crs)
