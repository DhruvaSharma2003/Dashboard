import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import json
import numpy as np
import geopandas as gpd
import sys # Import sys for object size checking

# Page setup
st.set_page_config(layout="wide", page_title="India FoodCrop Dashboard", page_icon="🌾")

# ---------- CSS ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700&display=swap');

html, body, [class*=\"css\"] {
    font-family: 'Poppins', sans-serif;
}
.toggle-container {
    display: flex;
    justify-content: center;
    gap: 2rem;
    margin: 2.5rem 0 1rem;
}
.toggle-button {
    font-size: 2rem;
    padding: 1.2rem 3rem;
    border-radius: 12px;
    border: 2px solid #ccc;
    background-color: white;
    color: black;
    font-weight: 700;
    cursor: pointer;
    transition: all 0.3s ease-in-out;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
}
.toggle-button:hover {
    transform: scale(1.1);
    background-color: #f0f0f0;
}
.toggle-button.selected {
    background-color: black;
    color: white;
    transform: scale(1.2);
}
.sidebar-title {
    background-color: white;
    padding: 1rem;
    font-size: 1.3rem;
    font-weight: 700;
    border-radius: 15px;
    margin-bottom: 1rem;
    text-align: center;
    color: #111;
}
</style>
""", unsafe_allow_html=True)

# ---------- SESSION STATE ----------
if "selected_type" not in st.session_state:
    st.session_state.selected_type = None


# Define a common mapping for state/UT names to ensure consistency
STATE_NAME_CORRECTIONS = {
    "Orissa": "Odisha",
    "Jammu & Kashmir": "Jammu and Kashmir",
    "Chhattisgarh": "Chhattishgarh",
    "Telangana": "Telengana", # Common historical spelling
    "Tamil Nadu": "Tamilnadu",
    "Kerela": "Kerala",
    "Andaman & Nicobar Islands": "Andaman & Nicobar", # Consistent UT name
    "Arunachal Pradesh": "Arunanchal Pradesh",
    "Dadra & Nagar Haveli": "Dadara & Nagar Havelli",
    "Delhi": "NCT of Delhi", # Specific for NCT
    "Puducherry": "Puducherry", # Ensure consistent spelling for Puducherry
    "Lakshadweep": "Lakshadweep", # Add Lakshadweep if it appears
    "Chandigarh": "Chandigarh", # Add Chandigarh if it appears
    "Daman & Diu": "Daman & Diu", # Add Daman & Diu if it appears
    "Ladakh": "Ladakh" # Add Ladakh if it appears (post 2019 UT)
}

# Define pulse units globally so they are always accessible
pulse_units = {
    "Area": "'000 Hectare",
    "Production": "'000 Tonne",
    "Yield": "Kg/Hectare"
}

# Global flags for data loading success
data_loaded_successfully = True

# --- Cached GeoDataFrame loading functions ---
@st.cache_data
def load_india_states_gdf(path="India_Shapefile/india_st.shp"):
    """
    Loads India states shapefile, normalizes state names, and returns a GeoDataFrame.
    Applies geometry simplification.
    """
    if not os.path.exists(path):
        st.error(f"Error: India states shapefile not found at '{path}'. Please ensure the file exists.")
        return None
    try:
        gdf = gpd.read_file(path)
        gdf["State_Name"] = gdf["State_Name"].str.strip().replace(STATE_NAME_CORRECTIONS).str.upper()
        # Apply simplification to state geometries
        # Tolerance value chosen to balance detail and file size (adjust as needed)
        # Larger tolerance means more simplification (smaller file, less detail)
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.005, preserve_topology=True)
        st.info(f"Successfully loaded {len(gdf)} state geometries from '{path}' (simplified).")
        st.info(f"Sample GeoDataFrame state names: {sorted(gdf['State_Name'].unique().tolist())[:5]}...")
        return gdf
    except Exception as e:
        st.exception(f"Error loading India states GeoDataFrame from '{path}': {e}")
        return None

@st.cache_data
def load_india_districts_shapefile():
    """
    Loads India districts shapefile, normalizes state names within it,
    and returns a GeoDataFrame. Applies geometry simplification.
    """
    path = "India_Shapefile/State/2011_Dist.shp"
    if not os.path.exists(path):
        st.error(f"Error: India districts shapefile not found at '{path}'. Please ensure the file exists.")
        return None
    try:
        gdf = gpd.read_file(path)
        gdf = gdf.set_crs(epsg=4326, inplace=False)
        gdf["ST_NM"] = gdf["ST_NM"].str.strip().replace(STATE_NAME_CORRECTIONS).str.upper()
        # Apply simplification to district geometries
        # Increased tolerance to 0.005 for more aggressive simplification to address MessageSizeError
        gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.005, preserve_topology=True)
        st.info(f"Successfully loaded {len(gdf)} district geometries from '{path}' (simplified).")
        st.info(f"Sample District shapefile state names: {sorted(gdf['ST_NM'].unique().tolist())[:5]}...")
        return gdf
    except Exception as e:
        st.exception(f"Error loading India districts shapefile from '{path}': {e}")
        return None

# Load GeoDataFrame for states and districts once
india_states_gdf = load_india_states_gdf()
gdf_districts = load_india_districts_shapefile()

# Check if GeoDataFrame data loaded successfully
if india_states_gdf is None or gdf_districts is None:
    data_loaded_successfully = False
    st.error("Map data (GeoDataFrames/Shapefiles) could not be loaded. Please check file paths and permissions.")
else:
    if 'ST_NM' in gdf_districts.columns:
        gdf_districts = gdf_districts[gdf_districts["ST_NM"] != "INDIA"].copy()
    else:
        st.warning("'ST_NM' column not found in district shapefile. Cannot filter 'INDIA' state.")

# Initialize df_pulses outside the try block
df_pulses = pd.DataFrame()
df_pulses_raw = pd.DataFrame()

# ---------- INDIA PULSES CHOROPLETH MAP ----------
st.subheader("🇮🇳 India Pulses Choropleth Map Over Time")

with st.sidebar:
    st.markdown("### 🌱 Pulses Map Settings")
    season = st.selectbox("Select Season", ["Kharif", "Rabi", "Total"])
    pulse_sheets = ["Gram", "Urad", "Moong", "Masoor", "Moth", "Kulthi", "Khesari", "Peas", "Arhar"]
    pulse_type = st.selectbox("Select Pulse Type", pulse_sheets)
    metric = st.selectbox("Select Metric", ["Area", "Production", "Yield"])

if data_loaded_successfully:
    try:
        excel_path = "Data/Pulses_Data.xlsx"
        if not os.path.exists(excel_path):
            st.error(f"Error: Pulses data Excel file not found at '{excel_path}'. Please ensure the file exists.")
            data_loaded_successfully = False
        else:
            df_pulses_raw = pd.read_excel(excel_path, sheet_name=pulse_type, header=1)
            st.info(f"Successfully loaded raw data for '{pulse_type}'. Original rows: {len(df_pulses_raw)}.")
            st.info(f"Raw df_pulses_raw columns: {df_pulses_raw.columns.tolist()}")
            st.info(f"Raw df_pulses_raw head:\n{df_pulses_raw.head().to_string()}")

            df_pulses_raw.columns = df_pulses_raw.columns.str.strip()
            df_pulses_raw = df_pulses_raw.rename(columns={"States/UTs": "State"})

            if "Season" in df_pulses_raw.columns:
                df_pulses_raw = df_pulses_raw[df_pulses_raw["Season"].str.lower() == season.lower()].copy()
                st.info(f"After Season filter, df_pulses_raw rows: {len(df_pulses_raw)}.")
            else:
                st.warning("Season column not found in pulses data. Check Excel structure.")
                df_pulses_raw = pd.DataFrame()

            if not df_pulses_raw.empty and "Year" in df_pulses_raw.columns:
                df_pulses_raw["Year_Processed"] = pd.to_numeric(df_pulses_raw["Year"].astype(str).str.split('-').str[0], errors='coerce')
                df_pulses_raw = df_pulses_raw.dropna(subset=["Year_Processed"]).copy()
                if not df_pulses_raw.empty:
                    df_pulses_raw["Year"] = df_pulses_raw["Year_Processed"].astype(int)
                    df_pulses_raw = df_pulses_raw.drop(columns=["Year_Processed"])
                else:
                    st.warning("No valid 'Year' data after processing. Check 'Year' column in Excel.")
                    df_pulses_raw = pd.DataFrame()
            elif not df_pulses_raw.empty:
                st.warning("Year column not found in pulses data. Check Excel structure.")
                df_pulses_raw = pd.DataFrame()

            if not df_pulses_raw.empty and metric in df_pulses_raw.columns:
                df_pulses_raw[metric] = pd.to_numeric(df_pulses_raw[metric], errors="coerce")
                df_pulses_raw = df_pulses_raw.dropna(subset=[metric]).copy()
                st.info(f"After Metric processing & NaN drop, df_pulses_raw rows: {len(df_pulses_raw)}.")
            elif not df_pulses_raw.empty:
                st.warning(f"Metric column '{metric}' not found in pulses data. Check Excel structure.")
                df_pulses_raw = pd.DataFrame()

            if not df_pulses_raw.empty and "State" in df_pulses_raw.columns:
                df_pulses_raw["State"] = df_pulses_raw["State"].str.strip().replace(STATE_NAME_CORRECTIONS).str.upper()
                st.info(f"Unique state names from Pulses Data (after normalization): {sorted(df_pulses_raw['State'].unique().tolist())}")
            elif not df_pulses_raw.empty:
                st.warning("State column not found in pulses data. Check Excel structure.")
                df_pulses_raw = pd.DataFrame()

            min_year = 0
            max_year = 0
            if not df_pulses_raw.empty and "Year" in df_pulses_raw.columns:
                min_year = int(df_pulses_raw["Year"].min())
                max_year = int(df_pulses_raw["Year"].max())
                st.info(f"Calculated year range from raw data: {min_year}-{max_year}")
            else:
                st.warning("Cannot determine year range. Decade selection will be unavailable.")
                data_loaded_successfully = False

            decade_options = []
            if min_year != 0 or max_year != 0:
                current_decade_start = (min_year // 10) * 10
                while current_decade_start <= max_year:
                    decade_end = current_decade_start + 9
                    if decade_end > max_year:
                        decade_end = max_year
                    decade_string = f"{current_decade_start}-{decade_end}"
                    decade_options.append(decade_string)
                    current_decade_start += 10

            selected_decade_range = None
            if decade_options:
                selected_decade_range = st.selectbox("Select Decade Range", decade_options)
                start_year_decade, end_year_decade = map(int, selected_decade_range.split('-'))
                df_pulses = df_pulses_raw[
                    (df_pulses_raw["Year"] >= start_year_decade) &
                    (df_pulses_raw["Year"] <= end_year_decade)
                ].copy()
                st.info(f"Data filtered for decade: {selected_decade_range}. Rows: {len(df_pulses)}. Years: {sorted(df_pulses['Year'].unique().tolist()) if not df_pulses.empty else 'None'}")
            else:
                st.warning("No complete decade ranges found. Check data or selections.")
                df_pulses = pd.DataFrame()
                data_loaded_successfully = False

            unit = pulse_units.get(metric, "Unit")
            title_suffix = f" in {selected_decade_range}" if selected_decade_range else "(No Decade Selected)"
            title = f"{pulse_type} - {season} - {metric} Over Time ({unit}){title_suffix}"

            if df_pulses.empty:
                st.warning("No data found for the selected Season, Pulse Type, Metric, and Decade. Please adjust your selections.")
            elif india_states_gdf is None:
                 st.warning("India states GeoDataFrame is not loaded. Cannot display map.")
            elif "State" not in df_pulses.columns or metric not in df_pulses.columns or "Year" not in df_pulses.columns:
                 st.warning("Required columns (State, Metric, Year) missing in filtered pulses data. Cannot display map.")
            else:
                fig_india_pulses = px.choropleth(
                    df_pulses,
                    geojson=india_states_gdf.geometry.__geo_interface__, # Use geometry interface
                    locations="State",
                    featureidkey="properties.State_Name", # Match against properties in the GeoDataFrame
                    color=metric,
                    hover_name="State",
                    animation_frame="Year",
                    color_continuous_scale="YlGnBu",
                    title=title,
                    labels={metric: unit}
                )

                fig_india_pulses.update_geos(fitbounds="locations", visible=False)
                fig_india_pulses.update_layout(
                    coloraxis_colorbar=dict(title=unit),
                    margin={"r": 0, "t": 40, "l": 0, "b": 0},
                    updatemenus=[{
                        "type": "buttons",
                        "buttons": [
                            {"label": "Play", "method": "animate", "args": [None, {"frame": {"duration": 200, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0, "easing": "linear"}}]},
                            {"label": "Pause", "method": "animate", "args": [[None], {"mode": "immediate", "frame": {"duration": 0}, "transition": {"duration": 0}}]}
                        ],
                        "direction": "left", "pad": {"r": 10, "t": 87}, "showactive": False, "x": 0.1, "xanchor": "right", "y": 0, "yanchor": "top"
                    }],
                    sliders=[{
                        "steps": [{"args": [[year], {"frame": {"duration": 200, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                                   "label": str(year), "method": "animate"} for year in sorted(df_pulses["Year"].unique())],
                        "active": 0, "transition": {"duration": 0}, "x": 0.1, "pad": {"b": 10, "t": 50}, "len": 0.9
                    }]
                )
                color_min = df_pulses[metric].min()
                color_max = df_pulses[metric].max()
                fig_india_pulses.update_coloraxes(cmin=color_min, cmax=color_max)

                st.plotly_chart(fig_india_pulses, use_container_width=True)

    except Exception as e:
        st.exception(e)
        st.error(f"An error occurred during India Pulses Map processing: {e}. Check data and selections.")
        df_pulses = pd.DataFrame()
        data_loaded_successfully = False
else:
    st.warning("Skipping India Pulses Map rendering due to previous data loading errors.")

if data_loaded_successfully and not df_pulses.empty and "State" in df_pulses.columns:
    available_states_for_dropdown = df_pulses["State"].unique().tolist()
else:
    available_states_for_dropdown = []

# ---------- STATE MAP VIEW ----------
st.sidebar.markdown("---")
st.sidebar.markdown("### 🗺️ State Map View")

state_options = ["None"] + sorted(available_states_for_dropdown)
selected_state_map = st.sidebar.selectbox("Select State for State Map", state_options)

state_col = None
district_col = None
if gdf_districts is not None and not gdf_districts.empty:
    for col in gdf_districts.columns:
        if "STATE" in col.upper() or "ST_NM" in col.upper():
            state_col = col
            break
    for col in gdf_districts.columns:
        if "DISTRICT" in col.upper() or "DIST_NAME" in col.upper() or "DIST_NM" in col.upper():
            district_col = col
            break

if data_loaded_successfully and selected_state_map != "None" and state_col and district_col:
    normalized_selected_state = selected_state_map.upper().replace(" ", "")
    if state_col in gdf_districts.columns:
        state_gdf_filtered = gdf_districts[
            gdf_districts[state_col].str.upper().str.replace(" ", "") == normalized_selected_state
        ].copy()
        st.info(f"State GeoDataFrame filtered for '{selected_state_map}'. Rows: {len(state_gdf_filtered)}")
    else:
        st.error(f"Missing expected column '{state_col}' in district shapefile for state filtering.")
        state_gdf_filtered = gpd.GeoDataFrame()

    if state_gdf_filtered.empty:
        st.warning(f"No district data found for {selected_state_map} in the district shapefile. Check state name consistency.")
    else:
        if not df_pulses.empty and "State" in df_pulses.columns and "Year" in df_pulses.columns and metric in df_pulses.columns:
            state_historical_df = df_pulses[
                df_pulses["State"].str.upper().str.replace(" ", "") == normalized_selected_state
            ].copy()
            st.info(f"State historical data (from df_pulses) for '{selected_state_map}'. Rows: {len(state_historical_df)}")
        else:
            st.warning("Pulses data (df_pulses) is empty or missing required columns for state historical data. Skipping state map plot.")
            state_historical_df = pd.DataFrame()

        if state_historical_df.empty:
            st.warning(f"No pulse data available for {selected_state_map} for {season} - {pulse_type} - {metric} over time within the selected decade. Skipping state map plot.")
        else:
            animated_state_district_data = []
            all_years_in_state_data = sorted(state_historical_df["Year"].unique())

            for year in all_years_in_state_data:
                current_year_state_data = state_historical_df[state_historical_df["Year"] == year]
                state_total_value = current_year_state_data[metric].values[0] if not current_year_state_data.empty else 0

                if district_col in state_gdf_filtered.columns:
                    districts_in_state = state_gdf_filtered[district_col].dropna().unique().tolist()
                else:
                    districts_in_state = []
                    st.warning(f"District column '{district_col}' not found in filtered state GeoDataFrame for data fabrication.")

                n_districts = len(districts_in_state)
                dummy_values_for_year = np.random.dirichlet(np.ones(n_districts)) * state_total_value if n_districts > 0 and pd.notna(state_total_value) else []

                temp_df = pd.DataFrame({
                    district_col: districts_in_state,
                    "Dummy_Value": dummy_values_for_year,
                    "Year": year
                })
                animated_state_district_data.append(temp_df)

            if animated_state_district_data:
                animated_state_district_df = pd.concat(animated_state_district_data, ignore_index=True)
                merged_district_gdf = state_gdf_filtered.merge(animated_state_district_df, left_on=district_col, right_on=district_col, how="left")
                st.info(f"Merged district GeoDataFrame rows for state map: {len(merged_district_gdf)}")
                st.info(f"Sample merged_district_gdf head for state map:\n{merged_district_gdf.head().to_string()}")

                st.markdown(f"### 📍 {selected_state_map} District Map - {metric} ({season}, {pulse_type})")

                fig_state_districts = px.choropleth(
                    merged_district_gdf,
                    geojson=merged_district_gdf.geometry.__geo_interface__, # Use geometry interface
                    locations=district_col,
                    featureidkey=f"properties.{district_col}", # Match against properties in the GeoDataFrame
                    color="Dummy_Value",
                    hover_name=district_col,
                    animation_frame="Year",
                    color_continuous_scale="YlOrRd",
                    title=f"{selected_state_map} District Map - {metric} ({season}, {pulse_type}) Over Time",
                    labels={"Dummy_Value": unit}
                )

                fig_state_districts.update_geos(fitbounds="locations", visible=False)
                fig_state_districts.update_layout(
                    coloraxis_colorbar=dict(title=unit),
                    margin={"r": 0, "t": 40, "l": 0, "b": 0},
                    updatemenus=[{
                        "type": "buttons",
                        "buttons": [
                            {"label": "Play", "method": "animate", "args": [None, {"frame": {"duration": 200, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0, "easing": "linear"}}]},
                            {"label": "Pause", "method": "animate", "args": [[None], {"mode": "immediate", "frame": {"duration": 0}, "transition": {"duration": 0}}]}
                        ],
                        "direction": "left", "pad": {"r": 10, "t": 87}, "showactive": False, "x": 0.1, "xanchor": "right", "y": 0, "yanchor": "top"
                    }],
                    sliders=[{
                        "steps": [{"args": [[year], {"frame": {"duration": 200, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                                   "label": str(year), "method": "animate"} for year in all_years_in_state_data],
                        "active": 0, "transition": {"duration": 0}, "x": 0.1, "pad": {"b": 10, "t": 50}, "len": 0.9
                    }]
                )
                color_min_dist = merged_district_gdf["Dummy_Value"].min()
                color_max_dist = merged_district_gdf["Dummy_Value"].max()
                fig_state_districts.update_coloraxes(cmin=color_min_dist, cmax=color_max_dist)
                st.plotly_chart(fig_state_districts, use_container_width=True)
            else:
                st.warning(f"Could not generate animated district map for {selected_state_map}. Animated data list was empty.")

        if not state_historical_df.empty and "Year" in state_historical_df.columns and metric in state_historical_df.columns:
            st.markdown(f"### Animated Historical Trend for {selected_state_map}")
            state_historical_df = state_historical_df.sort_values("Year")
            y_axis_title = f"{metric} ({pulse_units.get(metric, '')})"

            if not state_historical_df.empty and state_historical_df[metric].notna().any():
                all_years_for_line_plot = sorted(state_historical_df["Year"].unique())
                animation_frames_line = []
                for year in all_years_for_line_plot:
                    frame_data = state_historical_df[state_historical_df["Year"] <= year].copy()
                    frame_data["FrameYear"] = year
                    animation_frames_line.append(frame_data)
                animated_state_line_df = pd.concat(animation_frames_line, ignore_index=True)
                st.info(f"Animated state line data rows: {len(animated_state_line_df)}")

                if not animated_state_line_df.empty and metric in animated_state_line_df.columns:
                    y_min_state = animated_state_line_df[metric].min() * 0.95
                    y_max_state = animated_state_line_df[metric].max() * 1.05
                    x_min_state = animated_state_line_df["Year"].min()
                    x_max_state = animated_state_line_df["Year"].max()
                else:
                    y_min_state, y_max_state, x_min_state, x_max_state = 0, 1, 0, 1
                    st.warning("Could not determine axis limits for state historical plot. Data might be empty or missing metric column.")

                fig_state_trend = px.line(
                    animated_state_line_df,
                    x="Year", y=metric, animation_frame="FrameYear", animation_group="State",
                    title=f"Animated Trend of {metric} for {pulse_type} ({season}) in {selected_state_map}",
                    markers=True, labels={"Year": "Year", metric: y_axis_title, "FrameYear": "Year"},
                    range_y=[y_min_state, y_max_state], range_x=[x_min_state, x_max_state]
                )

                fig_state_trend.update_layout(
                    yaxis_title=y_axis_title, xaxis_title="Year",
                    font=dict(family="Poppins", size=12), title_font_size=18, legend_title="Metric",
                    sliders=[{'currentvalue': {'prefix': 'Year: '}, 'pad': {'t': 20}}],
                    updatemenus=[{'type': 'buttons', 'showactive': False, 'x': 0.05, 'y': -0.15,
                                  'buttons': [{'label': 'Play', 'method': 'animate', 'args': [None, {'frame': {'duration': 100, 'redraw': True}, 'fromcurrent': True, 'transition': {'duration': 0}}]},
                                              {'label': 'Pause', 'method': 'animate', "args": [[None], {'frame': {'duration': 50, 'redraw': False}, 'mode': 'immediate', 'transition': {'duration': 0}}]}]}]
                )
                fig_state_trend.update_layout({'sliders': [{'currentvalue': {'prefix': 'Year: '}, 'pad': {'t': 20}}]})
                st.plotly_chart(fig_state_trend, use_container_width=True)
            else:
                st.warning(f"No historical data with values for '{metric}' is available to plot a trend for {selected_state_map}. Animated data list was empty or missing metric.")
        else:
            st.warning(f"Required columns ('Year' or '{metric}') are missing in historical data for {selected_state_map}. Skipping state line plot.")
else:
    st.warning("Skipping State Map rendering due to previous data loading errors.")

# ---------- FULL INDIA DISTRICT MAP ----------
st.markdown("---")
st.subheader("�🇳 Full India District Map View (Fabricated Values)")

# This section needs `data_loaded_successfully` and also assumes `gdf_districts` is properly loaded.
if data_loaded_successfully and not df_pulses.empty and "Year" in df_pulses.columns and metric in df_pulses.columns and "State" in df_pulses.columns and gdf_districts is not None and not gdf_districts.empty:
    all_years_for_full_map = sorted(df_pulses["Year"].unique())
    st.info(f"Years for Full India District Map: {all_years_for_full_map}")

    # Create a base DataFrame to hold all fabricated district data for all years in the decade
    all_fabricated_district_data = []

    # Check for critical columns in gdf_districts before loop
    if not (district_col in gdf_districts.columns and state_col in gdf_districts.columns):
        st.error(f"Missing expected columns ('{district_col}' or '{state_col}') in gdf_districts for full map processing. Cannot generate map.")
        all_years_for_full_map = [] # Prevent loop from running

    for year in all_years_for_full_map:
        df_current_year_states = df_pulses[df_pulses["Year"] == year].copy()
        st.info(f"Processing Year: {year} for Full India District Map. States with data: {len(df_current_year_states)}")

        all_districts = gdf_districts[district_col].dropna().unique().tolist()
        year_dummy_data = {d: np.nan for d in all_districts} # Initialize with NaN

        for index, row in df_current_year_states.iterrows():
            state_name_from_data = row["State"]
            state_total_value = row[metric]

            normalized_state_name_data = state_name_from_data.upper().replace(" ", "")

            state_districts = gdf_districts[
                gdf_districts[state_col].str.upper().str.replace(" ", "") == normalized_state_name_data
            ][district_col].dropna().unique().tolist()

            n_districts = len(state_districts)

            if n_districts > 0 and pd.notna(state_total_value):
                proportions = np.random.dirichlet(np.ones(n_districts))
                dummy_values = proportions * state_total_value

                for i, district_name in enumerate(state_districts):
                    year_dummy_data[district_name] = dummy_values[i]
        
        df_year_fabricated = pd.DataFrame({
            district_col: list(year_dummy_data.keys()),
            "Dummy_Value": list(year_dummy_data.values()),
            "Year": year
        })
        all_fabricated_district_data.append(df_year_fabricated)

    if all_fabricated_district_data:
        combined_fabricated_data_df = pd.concat(all_fabricated_district_data, ignore_index=True)
        st.info(f"Combined fabricated data (DataFrame) rows: {len(combined_fabricated_data_df)}")
        st.info(f"Sample combined_fabricated_data_df head:\n{combined_fabricated_data_df.head().to_string()}")

        animated_full_india_districts_gdf = gdf_districts.merge(
            combined_fabricated_data_df,
            on=district_col,
            how="left"
        )
        st.info(f"Final animated_full_india_districts_gdf rows after merge: {len(animated_full_india_districts_gdf)}")
        st.info(f"Sample final animated_full_india_districts_gdf head:\n{animated_full_india_districts_gdf.head().to_string()}")

        # Check size of the GeoDataFrame before plotting
        geo_df_size_mb = sys.getsizeof(animated_full_india_districts_gdf) / (1024 * 1024)
        st.info(f"Size of animated_full_india_districts_gdf before plotting: {geo_df_size_mb:.2f} MB")


        fig_full_india_districts = px.choropleth(
            animated_full_india_districts_gdf,
            geojson=animated_full_india_districts_gdf.geometry.__geo_interface__, # Pass geometry interface
            locations=district_col,
            featureidkey=f"properties.{district_col}", # Match against properties in the GeoDataFrame
            color="Dummy_Value",
            hover_name=district_col,
            animation_frame="Year",
            color_continuous_scale="YlOrRd",
            title=f"Full India District Map - {metric} ({season}, {pulse_type}) Over Time (Fabricated Values)",
            labels={"Dummy_Value": unit}
        )

        fig_full_india_districts.update_geos(fitbounds="locations", visible=False)
        fig_full_india_districts.update_layout(
            coloraxis_colorbar=dict(title=unit),
            margin={"r": 0, "t": 40, "l": 0, "b": 0},
            updatemenus=[{
                "type": "buttons",
                "buttons": [
                    {"label": "Play", "method": "animate", "args": [None, {"frame": {"duration": 200, "redraw": True}, "fromcurrent": True, "transition": {"duration": 0, "easing": "linear"}}]},
                    {"label": "Pause", "method": "animate", "args": [[None], {"mode": "immediate", "frame": {"duration": 0}, "transition": {"duration": 0}}]}
                ],
                "direction": "left", "pad": {"r": 10, "t": 87}, "showactive": False, "x": 0.1, "xanchor": "right", "y": 0, "yanchor": "top"
            }],
            sliders=[{
                "steps": [{"args": [[year], {"frame": {"duration": 200, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                           "label": str(year), "method": "animate"} for year in all_years_for_full_map],
                "active": 0, "transition": {"duration": 0}, "x": 0.1, "pad": {"b": 10, "t": 50}, "len": 0.9
            }]
        )
        color_min_full = animated_full_india_districts_gdf["Dummy_Value"].min()
        color_max_full = animated_full_india_districts_gdf["Dummy_Value"].max()
        fig_full_india_districts.update_coloraxes(cmin=color_min_full, cmax=color_max_full)
        st.plotly_chart(fig_full_india_districts, use_container_width=True)
    else:
        st.warning("Could not generate animated full India district map. No fabricated data available.")
else:
    st.warning("Skipping Full India District Map rendering due to previous data loading errors or empty data.")


# ---------- DISTRICT-WISE ANIMATED HISTORICAL PLOT (RANDOM VALUES) ----------
st.markdown("---")
st.subheader("📽️ Animated District-wise Trend (Simulated Data)")

if selected_state_map != "None":
    if gdf_districts is not None and not gdf_districts.empty and state_col in gdf_districts.columns and district_col in gdf_districts.columns:
        filtered_districts_for_line_plot = gdf_districts[
            gdf_districts[state_col].str.upper().str.replace(" ", "") == normalized_selected_state
        ][district_col].dropna().unique().tolist()
        filtered_districts_for_line_plot = sorted(filtered_districts_for_line_plot)
        st.info(f"Filtered districts for line plot: {filtered_districts_for_line_plot}")
    else:
        st.warning("GeoDataFrame for districts is not loaded or missing required columns for district filter.")
        filtered_districts_for_line_plot = []
else:
    filtered_districts_for_line_plot = []

if filtered_districts_for_line_plot:
    selected_district_for_line_plot = st.sidebar.selectbox("🎯 Select a District for Trend Animation", filtered_districts_for_line_plot)
else:
    selected_district_for_line_plot = None
    st.sidebar.warning("No districts available for selected state for trend plot.")

if selected_district_for_line_plot:
    years_simulated = np.arange(2000, 2024)
    np.random.seed(42)
    random_values_simulated = np.random.uniform(low=50, high=300, size=len(years_simulated))

    district_trend_simulated_df = pd.DataFrame({
        "Year": years_simulated,
        "Value": random_values_simulated,
        "District": selected_district_for_line_plot
    })

    animation_frames_district_line_simulated = []
    for year in years_simulated:
        frame_df = district_trend_simulated_df[district_trend_simulated_df["Year"] <= year].copy()
        frame_df["FrameYear"] = year
        animation_frames_district_line_simulated.append(frame_df)

    animated_district_line_simulated_df = pd.concat(animation_frames_district_line_simulated, ignore_index=True)
    st.info(f"Animated simulated district line data rows: {len(animated_district_line_simulated_df)}")

    y_min_simulated = random_values_simulated.min() * 0.95
    y_max_simulated = random_values_simulated.max() * 1.05

    fig_district_trend_simulated = px.line(
        animated_district_line_simulated_df,
        x="Year", y="Value", animation_frame="FrameYear", animation_group="District",
        title=f"Animated Trend for {selected_district_for_line_plot} (Simulated, {years_simulated.min()}–{years_simulated.max()})",
        markers=True, labels={"Year": "Year", "Value": "Simulated Value", "FrameYear": "Year"},
        range_y=[y_min_simulated, y_max_simulated], range_x=[years_simulated.min(), years_simulated.max()]
    )

    fig_district_trend_simulated.update_layout(
        xaxis_title="Year", yaxis_title="Simulated Metric",
        font=dict(family="Poppins", size=12), title_font_size=18,
        sliders=[{'currentvalue': {'prefix': 'Year: '}, 'pad': {'t': 20}}],
        updatemenus=[{'type': 'buttons', 'showactive': False, 'x': 0.05, 'y': -0.15,
                      'buttons': [{'label': 'Play', 'method': 'animate', 'args': [None, {'frame': {'duration': 200, 'redraw': True}, 'fromcurrent': True, 'transition': {'duration': 0}}]},
                                  {'label': 'Pause', 'method': 'animate', "args": [[None], {'frame': {'duration': 50, 'redraw': False}, 'mode': 'immediate', 'transition': {'duration': 0}}]}]}]
    )
    st.plotly_chart(fig_district_trend_simulated, use_container_width=True)
else:
    st.info("Please select a state to view district-wise trend simulation.")
�
