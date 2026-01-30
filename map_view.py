import json
from typing import Dict, Optional

import pydeck as pdk
import streamlit as st


def map_style_for(style_choice: str) -> Optional[str]:
    """
    Return basemap style URL (for GL styles) or None for raster OSM tiles mode.
    """
    choice = (style_choice or "light").lower()

    carto_styles = {
        "light": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
        "dark": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    }

    if choice == "osm":
        # We'll use a TileLayer and disable map_style in Deck
        return None

    return carto_styles.get(choice, carto_styles["light"])


def _gdf_to_geojson_dict(gdf):
    if gdf is None or len(gdf) == 0:
        return None
    return json.loads(gdf.to_json())


def _decorate_isochrones_with_colors(iso_wgs84):
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
    return gj


def render_map(
    points_gdf=None,
    roads_gdf=None,
    iso_wgs84=None,
    zoom=10,
    map_style=None,
    split_iso_layers=False,
    show_chart=True,
    use_maplibre=True,
):
    layers = []
    base_layers = []

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
        gj = _decorate_isochrones_with_colors(iso_wgs84)

        if split_iso_layers and gj and "features" in gj:
            # Create one layer per distance for toggle control
            feats_by_d: Dict = {}
            for f in gj["features"]:
                d = f.get("properties", {}).get("dist_m")
                feats_by_d.setdefault(d, []).append(f)
            for d, flist in feats_by_d.items():
                layers.append(
                    pdk.Layer(
                        "GeoJsonLayer",
                        data={"type": "FeatureCollection", "features": flist},
                        pickable=True,
                        stroked=True,
                        filled=True,
                        extruded=False,
                        get_fill_color="properties.fill_color",
                        get_line_color=[0, 0, 0],
                        get_line_width=1,
                        visible=True,
                        id=f"iso_{d}",
                    )
                )
        else:
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
                    id="iso_all",
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

    # Basemap handling:
    # If map_style is None -> we use raster OSM tiles + disable GL basemap.
    use_osm_tiles = map_style is None

    if use_osm_tiles:
        base_layers.append(
            pdk.Layer(
                "TileLayer",
                data="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
                min_zoom=0,
                max_zoom=19,
                tile_size=256,
                attribution="© OpenStreetMap contributors",
            )
        )

    view_state = pdk.ViewState(longitude=center_lon, latitude=center_lat, zoom=zoom, pitch=0)

    deck = pdk.Deck(
        layers=base_layers + layers,
        initial_view_state=view_state,
        map_provider="maplibre" if use_maplibre else None,
        # In OSM tiles mode, disable map_style completely:
        map_style=None if use_osm_tiles else map_style or "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    )

    if show_chart:
        st.pydeck_chart(deck, use_container_width=True, height=780)
    return deck


def build_map_export_html(points_gdf, iso_wgs84, map_style_choice):
    """
    Render pydeck map to HTML string with layer toggles for each isochrone band.
    """
    export_deck = render_map(
        points_gdf=points_gdf,
        roads_gdf=None,
        iso_wgs84=iso_wgs84,
        zoom=10,
        map_style=map_style_for(map_style_choice),
        split_iso_layers=True,
        show_chart=False,
        use_maplibre=False,  # let default Mapbox GL bundle handle tiles in HTML export
    )
    layer_ids = [f"iso_{d}" for d in sorted({int(x) for x in iso_wgs84["dist_m"].unique()})]
    html_str = export_deck.to_html(as_string=True, notebook_display=False)
    controls_parts = [
        "<div id='iso-toggle-panel' style='position:fixed;top:10px;left:10px;z-index:9999;padding:8px 10px;background:rgba(0,0,0,0.5);color:white;border-radius:8px;font-family:sans-serif;'>"
    ]
    for lid in layer_ids:
        dist_val = lid.split("_")[1]
        controls_parts.append(
            f"<label style='display:block;font-size:12px;'><input type='checkbox' data-layer='{lid}' checked> {dist_val} m</label>"
        )
    controls_parts.append("</div>")
    controls_html = "".join(controls_parts)
    toggle_js = f"""
    <script>
    const layerIds = {layer_ids};
    const deckgl = window.deckgl;
    const panelWrap = document.createElement('div');
    panelWrap.innerHTML = `{controls_html}`;
    document.body.appendChild(panelWrap.firstChild);
    const inputs = Array.from(document.querySelectorAll('#iso-toggle-panel input[type=checkbox]'));
    const update = () => {{
      const active = new Set(inputs.filter(i=>i.checked).map(i=>i.dataset.layer));
      deckgl.setProps({{
        layers: deckgl.props.layers.map(l => {{
          if (active.has(l.id)) return {{...l, visible:true}};
          if (layerIds.includes(l.id)) return {{...l, visible:false}};
          return l;
        }})
      }});
    }};
    inputs.forEach(i => i.addEventListener('change', update));
    update();
    </script>
    """
    return html_str.replace("</body>", toggle_js + "</body>")
