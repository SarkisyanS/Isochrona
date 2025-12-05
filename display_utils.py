import streamlit as st


def preview_gdf(gdf, n=5, title=None):
    """
    Show a GeoDataFrame in Streamlit without Arrow/geometry issues.
    Converts geometry column to string just for display.
    """
    if gdf is None:
        return

    df = gdf.head(n).copy()
    if "geometry" in df.columns:
        df["geometry"] = df["geometry"].astype("string")
    if title:
        st.caption(title)
    st.dataframe(df)
