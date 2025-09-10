import streamlit as st
import pandas as pd
import pydeck as pdk
from typing import List
import json
import h3


_latlng_to_h3 = getattr(h3, "latlng_to_cell", None) or getattr(h3, "geo_to_h3")
_polygon_to_cells = getattr(h3, "polygon_to_cells", None) or getattr(h3, "polyfill")
_grid_disk = getattr(h3, "grid_disk", None) or getattr(h3, "k_ring")  # both exist

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
    Load the polygon rows from the uploaded CSV. Expected columns:
    - 'scale_of_polygon' (Global/Local)
    - 'geog' (GeoJSON string with a Polygon or MultiPolygon)
    """
    df = pd.read_csv(DATA_PATH)
    df = df.rename(columns={c: c.lower() for c in df.columns})
    if not {"scale_of_polygon", "geog"}.issubset(df.columns):
        raise ValueError("CSV must contain columns: scale_of_polygon, geog (as GeoJSON).")
    return df

@st.cache_data(ttl="2d")
def get_df_shape_2(scale: str) -> pd.DataFrame:
    """
    Returns a dataframe with a 'coordinates' column suitable for pydeck PolygonLayer.
    Assumes 'geog' contains GeoJSON. If MultiPolygon, flatten to list of rings.
    """
    df = load_polygon_rows().query("scale_of_polygon == @scale").copy()
    if df.empty:
        raise ValueError(f"No polygon found in CSV for scale_of_polygon = '{scale}'")

    def extract_rings(geojson_str: str):
        g = json.loads(geojson_str)
        if g.get("type") == "Polygon":
            # pydeck expects a list of rings -> g['coordinates'] (first ring = exterior)
            return g["coordinates"][0]
        elif g.get("type") == "MultiPolygon":
            # take the first polygon's exterior ring
            return g["coordinates"][0][0]
        else:
            raise ValueError(f"Unsupported GeoJSON type: {g.get('type')}")

    df["coordinates"] = df["geog"].apply(extract_rings)
    return df[["coordinates"]]

@st.cache_data(ttl="2d")
def polygon_geojson_for(scale: str) -> dict:
    """Return a simple GeoJSON Polygon for the selected scale (from the CSV)."""
    row = get_df_shape_2(scale).iloc[0]
    # H3 expects GeoJSON with [lon, lat]
    coords = row["coordinates"]
    return {"type": "Polygon", "coordinates": [coords]}

@st.cache_data(ttl="2d")
def df_from_h3_set(h3_set) -> pd.DataFrame:
    return pd.DataFrame({"H3": list(h3_set)})

@st.cache_data(ttl="2d")
def get_df_polyfill_2(res: int, scale: str) -> pd.DataFrame:
    """
    Precise fill: all hexes whose area covers the polygon (H3 polyfill).
    """
    gj = polygon_geojson_for(scale)
    # h3 v4: polygon_to_cells; v3: polyfill(geojson, res, geo_json_conformant=True)
    if _polygon_to_cells is getattr(h3, "polygon_to_cells", None):
        cells = _polygon_to_cells(gj, res)
    else:
        cells = _polygon_to_cells(gj, res, True)
    return df_from_h3_set(cells)

@st.cache_data(ttl="2d")
def get_df_coverage_2(res: int, scale: str) -> pd.DataFrame:
    """
    Outline coverage: boundary cells = polyfill minus interior.
    We mark cells whose at least one neighbor is outside the polyfill.
    This mimics a boundary-style "coverage" visualization.
    """
    poly = set(get_df_polyfill_2(res, scale)["H3"].tolist())
    boundary = set()
    for h in poly:
        # neighbors (v4: grid_disk(h, 1) includes the cell itself; v3: k_ring)
        neighs = _grid_disk(h, 1)
        # normalize to an iterable of neighbors (exclude self if present)
        neighs = set(neighs) - {h}
        if any(n not in poly for n in neighs):
            boundary.add(h)
    return df_from_h3_set(boundary)

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
