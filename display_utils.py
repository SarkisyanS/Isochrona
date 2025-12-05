import pandas as pd
import streamlit as st


def preview_gdf(gdf, n=5, title=None):
    """
    Show a GeoDataFrame in Streamlit without Arrow/geometry issues.
    Converts geometry column to string just for display.
    """
    if gdf is None:
        return

    df = gdf.head(n).copy()
    if hasattr(df, "geometry") and df.geometry.name in df.columns:
        geom_col = df.geometry.name
        df = pd.DataFrame(df)  # drop GeoDataFrame geometry semantics
        df[geom_col] = df[geom_col].apply(lambda g: g.wkt if g is not None else None)
    else:
        df = pd.DataFrame(df)
    if title:
        st.caption(title)
    st.dataframe(df)
