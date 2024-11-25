import streamlit as st
import pandas as pd
import pydeck as pdk
import branca.colormap as cm
from snowflake.snowpark import Session
from snowflake.snowpark.functions import col
from typing import List
import json
from PIL import Image

session = Session.builder.configs(st.secrets["geodemo"]).create()

col1, col2, col3 = st.columns(3)

with col1:
    poly_scale_2 = st.selectbox("Scale of polygon", ("Global", "Local"), index=1)
    if poly_scale_2 == 'Global':
        min_v_2, max_v_2, v_2, z_2, lon_2, lat_2 = 2, 5, 4, 2, -94.50284957885742, 38.51405689475766
    else:
        min_v_2, max_v_2, v_2, z_2, lon_2, lat_2 = 7, 10, 9, 9, -73.98452997207642, 40.74258515841464

with col2:
    original_shape_2 = st.selectbox("Show original shape", ("Yes", "No"),  index=0)

with col3:
    h3_res_2 = st.slider( "H3 resolution ", min_value=min_v_2, max_value=max_v_2, value=v_2)

@st.cache_resource(ttl="2d")
def get_df_shape_2(poly_scale_2: str) -> pd.DataFrame:
    df = session.sql(
        f"select geog from snowpublic.streamlit.h3_polygon_spherical where scale_of_polygon = '{poly_scale_2}'"
    ).to_pandas()
    df["coordinates"] = df["GEOG"].apply(lambda row: json.loads(row)["coordinates"][0])
    return df


@st.cache_resource(ttl="2d")
def get_layer_shape_2(df: pd.DataFrame, line_color: List) -> pdk.Layer:
    return pdk.Layer("PolygonLayer", 
                     df, 
                     opacity=0.9, 
                     stroked=True, 
                     get_polygon="coordinates",
                     filled=False,
                     extruded=False,
                     wireframe=True,
                     get_line_color=line_color,
                     line_width_min_pixels=1)

@st.cache_resource(ttl="2d")
def get_df_coverage_2(h3_res_2: float, poly_scale_2: str) -> pd.DataFrame:
    if poly_scale_2 == 'Global':
        return session.sql(
            f"select value::string as h3 from snowpublic.streamlit.h3_polygon_planar, TABLE(FLATTEN(h3_coverage_strings(to_geography('POLYGON((-118.389015198 34.092757508,-73.933868408 40.864977873,-78.47448349 33.898489435,-118.389015198 34.092757508))'), {h3_res_2})))"
        ).to_pandas()
    if poly_scale_2 == 'Local':
        return session.sql(
            f"select value::string as h3 from snowpublic.streamlit.h3_polygon_planar, TABLE(FLATTEN(h3_coverage_strings(to_geography('POLYGON((-73.819815516 40.783403069,-74.161494076 40.717999437,-73.835597634 40.727238441,-73.819815516 40.783403069))'), {h3_res_2}))) where scale_of_polygon = '{poly_scale_2}'"
        ).to_pandas()

@st.cache_resource(ttl="2d")
def get_layer_coverage_2(df_coverage_2: pd.DataFrame, line_color: List) -> pdk.Layer:
    return pdk.Layer("H3HexagonLayer", 
                     df_coverage_2, 
                     get_hexagon="H3", 
                     extruded=False,
                     stroked=True, 
                     filled=False, 
                     get_line_color=line_color, 
                     line_width_min_pixels=1)

@st.cache_resource(ttl="2d")
def get_df_polyfill_2(h3_res_2: float, poly_scale_2: str) -> pd.DataFrame:
    if poly_scale_2 == 'Global':
        return session.sql(
            f"select value::string as h3 from snowpublic.streamlit.h3_polygon_planar, TABLE(FLATTEN(h3_polygon_to_cells_strings(to_geography('POLYGON((-118.389015198 34.092757508,-73.933868408 40.864977873,-78.47448349 33.898489435,-118.389015198 34.092757508))'), {h3_res_2})))"
        ).to_pandas()
    if poly_scale_2 == 'Local':
        return session.sql(
            f"select value::string as h3 from snowpublic.streamlit.h3_polygon_planar, TABLE(FLATTEN(h3_polygon_to_cells_strings(to_geography('POLYGON((-73.819815516 40.783403069,-74.161494076 40.717999437,-73.835597634 40.727238441,-73.819815516 40.783403069))'), {h3_res_2}))) where scale_of_polygon = '{poly_scale_2}'"
        ).to_pandas()

@st.cache_resource(ttl="2d")
def get_layer_polyfill_2(df_polyfill_2: pd.DataFrame, line_color: List) -> pdk.Layer:
    return pdk.Layer("H3HexagonLayer", 
                     df_polyfill_2, 
                     get_hexagon="H3", 
                     extruded=False,
                     stroked=True, 
                     filled=False, 
                     get_line_color=line_color, 
                     line_width_min_pixels=1)

df_shape_2 = get_df_shape_2(poly_scale_2)
layer_shape_2 = get_layer_shape_2(df_shape_2, [217, 102, 255])

df_coverage_2 = get_df_coverage_2(h3_res_2, poly_scale_2)
layer_coverage_2 = get_layer_coverage_2(df_coverage_2, [18, 100, 129])

df_polyfill_2 = get_df_polyfill_2(h3_res_2, poly_scale_2)
layer_polyfill_2 = get_layer_polyfill_2(df_polyfill_2, [36, 191, 242])

if original_shape_2 == "Yes":
    visible_layers_coverage_2 = [layer_coverage_2, layer_shape_2]
    visible_layers_polyfill_2 = [layer_polyfill_2, layer_shape_2]
else:
    visible_layers_coverage_2 = [layer_coverage_2]
    visible_layers_polyfill_2 = [layer_polyfill_2]

col1, col2 = st.columns(2)

with col1:
    st.pydeck_chart(pdk.Deck(map_provider='carto', map_style='light',
                             initial_view_state=pdk.ViewState(
                                 latitude=lat_2,
                                 longitude=lon_2, 
                                 zoom=z_2, 
                                 width = 350, 
                                 height = 250),
                             layers=visible_layers_coverage_2))
    st.caption('H3_COVERAGE')

with col2:
    st.pydeck_chart(pdk.Deck(map_provider='carto', map_style='light',
                             initial_view_state=pdk.ViewState(
                                 latitude=lat_2,
                                 longitude=lon_2,
                                 zoom=z_2, 
                                 width = 350, 
                                 height = 250),
                             layers=visible_layers_polyfill_2))
    st.caption('H3_POLYGON_TO_CELLS')
