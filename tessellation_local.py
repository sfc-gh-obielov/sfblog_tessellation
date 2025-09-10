import streamlit as st
import pandas as pd
import pydeck as pdk
from typing import List
import json

import h3

_has_polygon_class = hasattr(h3, "Polygon")
_has_polygon_to_cells = hasattr(h3, "polygon_to_cells")
_has_polyfill = hasattr(h3, "polyfill")
_grid_disk = getattr(h3, "grid_disk", None) or getattr(h3, "k_ring")

def _geojson_to_exterior_lonlat(geojson_str: str):
    """Return exterior ring as list[[lon,lat], ...] from a Polygon/MultiPolygon GeoJSON string."""
    g = json.loads(geojson_str)
    t = g.get("type")
    if t == "Polygon":
        return g["coordinates"][0]
    elif t == "MultiPolygon":
        return g["coordinates"][0][0]  # take first polygon's exterior
    else:
        raise ValueError(f"Unsupported GeoJSON type: {t}")

def _polyfill_compat(exterior_lonlat, res: int):
    """Return a set of H3 indices covering the polygon (polyfill) for H3 v4 or v3."""
    if _has_polygon_class and _has_polygon_to_cells:
        # v4 string API expects Polygon with (lat,lng) tuples
        exterior_latlng = [(lat, lon) for lon, lat in exterior_lonlat]
        poly = h3.Polygon(exterior=exterior_latlng, holes=[])
        return set(h3.polygon_to_cells(poly, res))
    elif _has_polyfill:
        # v3 API expects GeoJSON with [lon,lat]
        gj = {"type": "Polygon", "coordinates": [exterior_lonlat]}
        return set(h3.polyfill(gj, res, True))
    else:
        raise RuntimeError("No compatible H3 polyfill available in this environment.")

def _boundary_from_polyfill(poly_cells: set) -> set:
    """Cells on the boundary: at least one neighbor is outside the polyfill."""
    boundary = set()
    for h in poly_cells:
        neighs = set(_grid_disk(h, 1)) - {h}  # neighbors only
        if any(n not in poly_cells for n in neighs):
            boundary.add(h)
    return boundary

# ---- App config ----
DATA_PATH = "data/h3_polygon_spherical.csv"  # uploaded dataset

# ---------------- UI ----------------
col1, col2, col3 = st.columns(3)
with col1:
    poly_scale_2 = st.selectbox("Scale of polygon", ("Global", "Local"), index=1)
    if poly_scale_2 == "Global":
        min_v_2, max_v_2, v_2, z_2, lon_2, lat_2 = 2, 5, 4, 2, -94.50284957885742, 38.51405689475766
    else:
        min_v_2, max_v_2, v_2, z_2, lon_2, lat_2 = 7, 10, 9, 9, -73.98452997207642, 40.74258515841464

with col2:
    original_shape_2 = st.selectbox("Show original shape", ("Yes", "No"), index=0)

with col3:
    h3_res_2 = st.slider("H3 resolution ", min_value=min_v_2, max_value=max_v_2, value=v_2, step=1)

# ---------------- Data loading & transforms ----------------
@st.cache_data(ttl="2d")
def load_polygon_rows() -> pd.DataFrame:
    """
    Expect columns:
      - scale_of_polygon: 'Global' or 'Local'
      - geog: GeoJSON string (Polygon or MultiPolygon)
    """
    df = pd.read_csv(DATA_PATH)
    df.columns = [c.lower() for c in df.columns]
    if not {"scale_of_polygon", "geog"}.issubset(df.columns):
        raise ValueError("CSV must contain columns: scale_of_polygon, geog")
    return df

@st.cache_data(ttl="2d")
def get_df_shape_2(scale: str) -> pd.DataFrame:
    df = load_polygon_rows().query("scale_of_polygon == @scale").copy()
    if df.empty:
        raise ValueError(f"No polygon found in CSV for scale_of_polygon = '{scale}'")
    exterior_lonlat = _geojson_to_exterior_lonlat(df.iloc[0]["geog"])
    df_out = pd.DataFrame({"coordinates": [exterior_lonlat]})
    return df_out

@st.cache_data(ttl="2d")
def get_df_polyfill_2(res: int, scale: str) -> pd.DataFrame:
    exterior_lonlat = _geojson_to_exterior_lonlat(
        load_polygon_rows().query("scale_of_polygon == @scale").iloc[0]["geog"]
    )
    cells = _polyfill_compat(exterior_lonlat, res)
    return pd.DataFrame({"H3": list(cells)})

@st.cache_data(ttl="2d")
def get_df_coverage_2(res: int, scale: str) -> pd.DataFrame:
    poly_cells = set(get_df_polyfill_2(res, scale)["H3"])
    boundary = _boundary_from_polyfill(poly_cells)
    return pd.DataFrame({"H3": list(boundary)})

# ---------------- Layers ----------------
@st.cache_data(ttl="2d")
def get_layer_shape_2(df: pd.DataFrame, line_color: List[int]) -> pdk.Layer:
    return pdk.Layer(
        "PolygonLayer",
        df,
        opacity=0.9,
        stroked=True,
        get_polygon="coordinates",
        filled=False,
        extruded=False,
        wireframe=True,
        get_line_color=line_color,
        line_width_min_pixels=1,
    )

@st.cache_data(ttl="2d")
def get_layer_h3(df: pd.DataFrame, line_color: List[int]) -> pdk.Layer:
    return pdk.Layer(
        "H3HexagonLayer",
        df,
        get_hexagon="H3",
        extruded=False,
        stroked=True,
        filled=False,
        get_line_color=line_color,
        line_width_min_pixels=1,
        pickable=True,
    )

# ---------------- Build data & render ----------------
df_shape_2 = get_df_shape_2(poly_scale_2)
layer_shape_2 = get_layer_shape_2(df_shape_2, [217, 102, 255])

df_coverage_2 = get_df_coverage_2(h3_res_2, poly_scale_2)
layer_coverage_2 = get_layer_h3(df_coverage_2, [18, 100, 129])

df_polyfill_2 = get_df_polyfill_2(h3_res_2, poly_scale_2)
layer_polyfill_2 = get_layer_h3(df_polyfill_2, [36, 191, 242])

if original_shape_2 == "Yes":
    visible_layers_coverage_2 = [layer_coverage_2, layer_shape_2]
    visible_layers_polyfill_2 = [layer_polyfill_2, layer_shape_2]
else:
    visible_layers_coverage_2 = [layer_coverage_2]
    visible_layers_polyfill_2 = [layer_polyfill_2]

colA, colB = st.columns(2)
with colA:
    st.pydeck_chart(
        pdk.Deck(
            map_provider="carto",
            map_style="light",
            initial_view_state=pdk.ViewState(
                latitude=lat_2, longitude=lon_2, zoom=z_2, width=350, height=250
            ),
            layers=visible_layers_coverage_2,
            tooltip={"html": "<b>ID:</b> {H3}", "style": {"color": "white"}},
        )
    )
    st.caption("H3_COVERAGE (boundary)")

with colB:
    st.pydeck_chart(
        pdk.Deck(
            map_provider="carto",
            map_style="light",
            initial_view_state=pdk.ViewState(
                latitude=lat_2, longitude=lon_2, zoom=z_2, width=350, height=250
            ),
            layers=visible_layers_polyfill_2,
            tooltip={"html": "<b>ID:</b> {H3}", "style": {"color": "white"}},
        )
    )
    st.caption("H3_POLYGON_TO_CELLS (polyfill)")
