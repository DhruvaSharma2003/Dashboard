import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import json
import numpy as np
import geopandas as gpd

# Page setup
st.set_page_config(layout="wide", page_title="India FoodCrop Dashboard", page_icon="🌾")

# ---------- CSS ----------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@600;700&display=swap');

html, body, [class*="css"] {
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


# --- Cached GeoJSON loading functions ---
@st.cache_data
def load_india_states_geojson(path="India_Shapefile/india_st.shp"):
    """
    Loads India states shapefile, normalizes state names, and converts it
    to GeoJSON format suitable for Plotly.
    """
    gdf = gpd.read_file(path)
    # Ensure consistent state names for merging with data
    gdf["State_Name"] = gdf["State_Name"].str.strip().replace(STATE_NAME_CORRECTIONS).str.upper() # Apply corrections and convert to uppercase
    return json.loads(gdf.to_json())

@st.cache_data
def load_india_districts_shapefile():
    """
    Loads India districts shapefile, normalizes state names within it,
    and returns a GeoDataFrame.
    """
    gdf = gpd.read_file("India_Shapefile/State/2011_Dist.shp")
    gdf = gdf.set_crs(epsg=4326, inplace=False)
    # Normalize state names in the district shapefile as well
    gdf["ST_NM"] = gdf["ST_NM"].str.strip().replace(STATE_NAME_CORRECTIONS).str.upper() # Apply corrections and convert to uppercase
    return gdf

# Load GeoJSON data for states and districts once
india_states_geojson = load_india_states_geojson()
gdf_districts = load_india_districts_shapefile()

# Filter out "India" if it somehow made it into state names in district shapefile
gdf_districts = gdf_districts[gdf_districts["ST_NM"] != "INDIA"]

# Initialize df_pulses outside the try block
df_pulses = pd.DataFrame()

# ---------- INDIA PULSES CHOROPLETH MAP ----------
st.subheader("🇮🇳 India Pulses Choropleth Map Over Time")

with st.sidebar:
    st.markdown("### 🌱 Pulses Map Settings")
    season = st.selectbox("Select Season", ["Kharif", "Rabi", "Total"])

    pulse_sheets = ["Gram", "Urad", "Moong", "Masoor", "Moth", "Kulthi", "Khesari", "Peas", "Arhar"]
    pulse_type = st.selectbox("Select Pulse Type", pulse_sheets)

    metric = st.selectbox("Select Metric", ["Area", "Production", "Yield"])

try:
    # Read the data from Excel
    df_pulses_raw = pd.read_excel( # Renamed to df_pulses_raw to keep original
        "Data/Pulses_Data.xlsx",
        sheet_name=pulse_type,
        header=1 # Header is in the second row (row 2 in Excel)
    )

    # Clean and preprocess data
    df_pulses_raw.columns = df_pulses_raw.columns.str.strip()
    df_pulses_raw = df_pulses_raw.rename(columns={"States/UTs": "State"})
    df_pulses_raw = df_pulses_raw[df_pulses_raw["Season"].str.lower() == season.lower()].copy() # Filter by season and create a copy

    # Drop rows where 'Year' is NaN before attempting to convert to int
    df_pulses_raw = df_pulses_raw.dropna(subset=["Year"])

    # Parse 'Year' column: take the first part if it's a range (e.g., "2000-01" -> 2000)
    df_pulses_raw["Year"] = df_pulses_raw["Year"].astype(str).str.split('-').str[0].astype(int)
    df_pulses_raw[metric] = pd.to_numeric(df_pulses_raw[metric], errors="coerce") # Coerce metric column to numeric
    df_pulses_raw = df_pulses_raw.dropna(subset=[metric]) # Drop rows where the metric is missing

    # Normalize state names in the DataFrame for consistent merging with GeoJSON
    df_pulses_raw["State"] = df_pulses_raw["State"].str.strip().replace(STATE_NAME_CORRECTIONS).str.upper() # Apply corrections and convert to uppercase

    # Determine available years and create decade ranges
    if not df_pulses_raw.empty:
        min_year = int(df_pulses_raw["Year"].min())
        max_year = int(df_pulses_raw["Year"].max())
    else:
        min_year = 0
        max_year = 0

    # Generate decade options
    decade_options = []
    if min_year != 0 or max_year != 0: # Only generate decades if there's actual data
        current_decade_start = (min_year // 10) * 10
        while current_decade_start <= max_year:
            decade_end = current_decade_start + 9
            if decade_end > max_year: # If the decade extends beyond max_year, clip it
                decade_end = max_year
            decade_string = f"{current_decade_start}-{decade_end}"
            decade_options.append(decade_string)
            current_decade_start += 10 # Move to the next decade

    # Add a dropdown for decade selection
    # Only show dropdown if there are valid decade options
    if decade_options:
        selected_decade_range = st.selectbox("Select Decade Range", decade_options)
        # Filter df_pulses based on the selected decade range
        start_year_decade, end_year_decade = map(int, selected_decade_range.split('-'))
        df_pulses = df_pulses_raw[
            (df_pulses_raw["Year"] >= start_year_decade) &
            (df_pulses_raw["Year"] <= end_year_decade)
        ].copy() # Use a copy to avoid modifying the raw DataFrame for other uses
    else:
        st.warning("No complete decade ranges found for the selected filters.")
        df_pulses = pd.DataFrame() # Ensure df_pulses is empty if no decades are generated

    # Determine unit for the map title and colorbar
    pulse_units = {
        "Area": "'000 Hectare",
        "Production": "'000 Tonne",
        "Yield": "Kg/Hectare"
    }
    unit = pulse_units.get(metric, "Unit") # Default to "Unit" if not found
    title = f"{pulse_type} - {season} - {metric} Over Time ({unit}) in {selected_decade_range if 'selected_decade_range' in locals() else 'All Years'}"

    # Check if df_pulses is empty after filtering
    if df_pulses.empty:
        st.warning("No data found for the selected Season, Pulse Type, Metric, and Decade. Please adjust your selections.")
    else:
        # Create choropleth map with animation using Plotly Express
        fig_india_pulses = px.choropleth(
            df_pulses,
            geojson=india_states_geojson,
            locations="State", # Column in df_pulses with state names
            featureidkey="properties.State_Name", # Property in GeoJSON for matching state names
            color=metric, # Column to determine color
            hover_name="State", # Column for hover information
            animation_frame="Year", # Column to animate over
            color_continuous_scale="YlGnBu", # Color scale
            title=title, # Map title
            labels={metric: unit} # Set colorbar label
        )

        # Layout adjustments for the map
        fig_india_pulses.update_geos(fitbounds="locations", visible=False) # Fit map to India bounds
        fig_india_pulses.update_layout(
            coloraxis_colorbar=dict(title=unit), # Colorbar title
            margin={"r": 0, "t": 40, "l": 0, "b": 0}, # Margins
            updatemenus=[{ # Play/Pause buttons
                "type": "buttons",
                "buttons": [
                    {
                        "label": "Play",
                        "method": "animate",
                        "args": [None, {
                            "frame": {"duration": 200, "redraw": True}, # Animation speed
                            "fromcurrent": True,
                            "transition": {"duration": 0, "easing": "linear"}
                        }]
                    },
                    {
                        "label": "Pause",
                        "method": "animate",
                        "args": [[None], {
                            "mode": "immediate", # Immediate stop on pause
                            "frame": {"duration": 0},
                            "transition": {"duration": 0}
                        }]
                    }
                ],
                "direction": "left",
                "pad": {"r": 10, "t": 87},
                "showactive": False,
                "x": 0.1,
                "xanchor": "right",
                "y": 0,
                "yanchor": "top"
            }],
            sliders=[{ # Year slider
                "steps": [
                    {"args": [[year], {"frame": {"duration": 200, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                     "label": str(year), "method": "animate"}
                    for year in sorted(df_pulses["Year"].unique()) # Steps for each unique year within the selected decade
                ],
                "active": 0, # Start at the first year
                "transition": {"duration": 0},
                "x": 0.1,
                "pad": {"b": 10, "t": 50},
                "len": 0.9 # Length of the slider
            }]
        )
        # Ensure a consistent range for the color axis across all frames
        color_min = df_pulses[metric].min()
        color_max = df_pulses[metric].max()
        fig_india_pulses.update_coloraxes(cmin=color_min, cmax=color_max)

        st.plotly_chart(fig_india_pulses, use_container_width=True)

except Exception as e:
    st.error(f"An error occurred loading India Pulses Map: {e}. Please check your data and selections.")
    df_pulses = pd.DataFrame() # Ensure df_pulses is an empty DataFrame on error


# This DataFrame contains all states and years for the selected season/pulse type.
# It's used to populate the state selection dropdown dynamically.
# Ensure this is only run if df_pulses is not empty from the try-except block
if 'df_pulses' in locals() and not df_pulses.empty:
    available_states_for_dropdown = df_pulses["State"].unique().tolist()
else:
    available_states_for_dropdown = []


# ---------- STATE MAP VIEW ----------
st.sidebar.markdown("---")
st.sidebar.markdown("### 🗺️ State Map View")

# Dropdown to select a state for detailed district map view
state_options = ["None"] + sorted(available_states_for_dropdown)
selected_state_map = st.sidebar.selectbox("Select State for State Map", state_options)

# Auto detect STATE and DISTRICT columns in the district shapefile
state_col = None
district_col = None
for col in gdf_districts.columns:
    if "STATE" in col.upper() or "ST_NM" in col.upper():
        state_col = col
        break
for col in gdf_districts.columns:
    if "DISTRICT" in col.upper() or "DIST_NAME" in col.upper() or "DIST_NM" in col.upper():
        district_col = col
        break


# Proceed only if a valid state is selected from the dropdown
if selected_state_map != "None":
    if state_col is None or district_col is None:
        st.error("Could not detect STATE or DISTRICT column in shapefile!")
    else:
        # Filter the district GeoDataFrame for the selected state
        # Normalize selected state name and GeoDataFrame state names for matching
        normalized_selected_state = selected_state_map.upper().replace(" ", "")
        state_gdf_filtered = gdf_districts[
            gdf_districts[state_col].str.upper().str.replace(" ", "") == normalized_selected_state
        ].copy() # Create a copy to avoid SettingWithCopyWarning

        if state_gdf_filtered.empty:
            st.warning(f"No district data found for {selected_state_map}. Please check state name consistency.")
        else:
            # Get historical data for the selected state from the main df_pulses DataFrame
            state_historical_df = df_pulses[ # Uses the already filtered df_pulses
                df_pulses["State"].str.upper().str.replace(" ", "") == normalized_selected_state
            ].copy()

            if state_historical_df.empty:
                st.warning(f"No pulse data available for {selected_state_map} for {season} - {pulse_type} - {metric} over time within the selected decade.")
            else:
                # Prepare a list to store data for animated district map (for all years)
                animated_state_district_data = []

                # Get all unique years present in the selected state's data
                all_years_in_state_data = sorted(state_historical_df["Year"].unique())

                for year in all_years_in_state_data:
                    # Get the state's total value for the current year
                    current_year_state_data = state_historical_df[state_historical_df["Year"] == year]
                    if not current_year_state_data.empty:
                        state_total_value = current_year_state_data[metric].values[0]
                    else:
                        state_total_value = 0 # Default to 0 if no data for a specific year

                    # Fabricate values for districts within the selected state for the current year
                    districts_in_state = state_gdf_filtered[district_col].dropna().unique().tolist()
                    n_districts = len(districts_in_state)

                    if n_districts > 0:
                        # Use Dirichlet distribution to create random proportions that sum to 1
                        proportions = np.random.dirichlet(np.ones(n_districts))
                        dummy_values_for_year = proportions * state_total_value
                    else:
                        dummy_values_for_year = [] # No districts, no dummy values

                    # Create a temporary DataFrame for this year's districts and values
                    temp_df = pd.DataFrame({
                        district_col: districts_in_state,
                        "Dummy_Value": dummy_values_for_year,
                        "Year": year # Add the year column for animation
                    })
                    animated_state_district_data.append(temp_df)

                if animated_state_district_data:
                    # Concatenate all annual dataframes to create the full animated dataset
                    animated_state_district_df = pd.concat(animated_state_district_data, ignore_index=True)

                    # Merge district geometries with the animated data (left merge to keep all geometries)
                    merged_district_gdf = state_gdf_filtered.merge(
                        animated_state_district_df,
                        left_on=district_col,
                        right_on=district_col,
                        how="left"
                    )

                    # Convert the merged GeoDataFrame to GeoJSON dictionary for Plotly Express
                    state_districts_geojson = json.loads(merged_district_gdf.to_json())

                    st.markdown(f"### 📍 {selected_state_map} District Map - {metric} ({season}, {pulse_type})")

                    # Create animated choropleth map for the selected state's districts
                    fig_state_districts = px.choropleth(
                        merged_district_gdf,
                        geojson=state_districts_geojson,
                        locations=district_col,
                        featureidkey=f"properties.{district_col}", # Match district name in GeoJSON properties
                        color="Dummy_Value", # Fabricated value for color
                        hover_name=district_col,
                        animation_frame="Year",
                        color_continuous_scale="YlOrRd",
                        title=f"{selected_state_map} District Map - {metric} ({season}, {pulse_type}) Over Time",
                        labels={"Dummy_Value": unit} # Colorbar label
                    )

                    # Layout adjustments for the state district map
                    fig_state_districts.update_geos(fitbounds="locations", visible=False)
                    fig_state_districts.update_layout(
                        coloraxis_colorbar=dict(title=unit),
                        margin={"r": 0, "t": 40, "l": 0, "b": 0},
                        updatemenus=[{ # Play/Pause buttons
                            "type": "buttons",
                            "buttons": [
                                {
                                    "label": "Play",
                                    "method": "animate",
                                    "args": [None, {
                                        "frame": {"duration": 200, "redraw": True},
                                        "fromcurrent": True,
                                        "transition": {"duration": 0, "easing": "linear"}
                                    }]
                                },
                                {
                                    "label": "Pause",
                                    "method": "animate",
                                    "args": [[None], {
                                        "mode": "immediate",
                                        "frame": {"duration": 0},
                                        "transition": {"duration": 0}
                                    }]
                                }
                            ],
                            "direction": "left",
                            "pad": {"r": 10, "t": 87},
                            "showactive": False,
                            "x": 0.1,
                            "xanchor": "right",
                            "y": 0,
                            "yanchor": "top"
                        }],
                        sliders=[{ # Year slider for state districts
                            "steps": [
                                {"args": [[year], {"frame": {"duration": 200, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                                 "label": str(year), "method": "animate"}
                                for year in all_years_in_state_data
                            ],
                            "active": 0,
                            "transition": {"duration": 0},
                            "x": 0.1,
                            "pad": {"b": 10, "t": 50},
                            "len": 0.9
                        }]
                    )
                    # Ensure a consistent range for the color axis across all frames
                    color_min_dist = merged_district_gdf["Dummy_Value"].min()
                    color_max_dist = merged_district_gdf["Dummy_Value"].max()
                    fig_state_districts.update_coloraxes(cmin=color_min_dist, cmax=color_max_dist)


                    st.plotly_chart(fig_state_districts, use_container_width=True)
                else:
                    st.warning(f"Could not generate animated district map for {selected_state_map}.")


            # ---------- STATE-WISE ANIMATED HISTORICAL PLOT (LINE CHART) ----------
            # This section generates a line chart showing historical trends for the selected state.
            # This part remains largely similar to the original code.
            if not state_historical_df.empty:
                st.markdown(f"### Animated Historical Trend for {selected_state_map}")

                state_historical_df = state_historical_df.sort_values("Year")

                pulse_units = {
                    "Area": "'000 Hectare",
                    "Production": "'000 Tonne",
                    "Yield": "Kg/Hectare"
                }
                y_axis_title = f"{metric} ({pulse_units.get(metric, '')})"

                if not state_historical_df.empty and state_historical_df[metric].notna().any():

                    all_years_for_line_plot = sorted(state_historical_df["Year"].unique())
                    animation_frames_line = []

                    # Prepare cumulative data for line chart animation
                    for year in all_years_for_line_plot:
                        frame_data = state_historical_df[state_historical_df["Year"] <= year].copy()
                        frame_data["FrameYear"] = year # This column drives the animation
                        animation_frames_line.append(frame_data)

                    animated_state_line_df = pd.concat(animation_frames_line, ignore_index=True)

                    # Set fixed axis limits for stable animation view
                    y_min_state = state_historical_df[metric].min() * 0.95
                    y_max_state = state_historical_df[metric].max() * 1.05
                    x_min_state = state_historical_df["Year"].min()
                    x_max_state = state_historical_df["Year"].max()

                    # Create the animated line plot
                    fig_state_trend = px.line(
                        animated_state_line_df,
                        x="Year",
                        y=metric,
                        animation_frame="FrameYear",   # Use the frame column to animate
                        animation_group="State",       # Ensures the line is continuous
                        title=f"Animated Trend of {metric} for {pulse_type} ({season}) in {selected_state_map}",
                        markers=True,
                        labels={"Year": "Year", metric: y_axis_title, "FrameYear": "Year"},
                        range_y=[y_min_state, y_max_state],
                        range_x=[x_min_state, x_max_state]
                    )

                    # Customize Layout and Animation Controls for the line chart
                    fig_state_trend.update_layout(
                        yaxis_title=y_axis_title,
                        xaxis_title="Year",
                        font=dict(family="Poppins, sans-serif", size=12),
                        title_font_size=18,
                        legend_title="Metric",
                        sliders=[{ # Year slider for line chart
                            'currentvalue': {'prefix': 'Year: '},
                            'pad': {'t': 20}
                        }],
                        updatemenus=[{ # Play/Pause buttons for line chart
                            'type': 'buttons',
                            'showactive': False,
                            'x': 0.05,
                            'y': -0.15,
                            'buttons': [{
                                'label': 'Play',
                                'method': 'animate',
                                'args': [None, {
                                    'frame': {'duration': 100, 'redraw': True},
                                    'fromcurrent': True,
                                    'transition': {'duration': 0}
                                }]
                            }, {
                            'label': 'Pause',
                            'method': 'animate',
                            'args': [[None], {
                                'frame': {'duration': 50, 'redraw': False},
                                'mode': 'immediate',
                                'transition': {'duration': 0}
                            }]
                            }]
                        }]
                    )

                    fig_state_trend.update_layout({
                        'sliders': [{'currentvalue': {'prefix': 'Year: '}, 'pad': {'t': 20}}]
                    })

                    st.plotly_chart(fig_state_trend, use_container_width=True)
                else:
                    st.warning(f"No historical data with values for '{metric}' is available to plot a trend for {selected_state_map}.")


# ---------- FULL INDIA DISTRICT MAP ----------
st.markdown("---")
st.subheader("🇮🇳 Full India District Map View (Fabricated Values)")

# This map will also be animated over years, showing fabricated district data.
# It uses the df_pulses (which contains data for all years) to get state totals for each year.

# Prepare a comprehensive DataFrame that holds all districts, for all years, with their fabricated values.
animated_full_india_district_data = []

# Get all unique years from the main df_pulses dataframe
# Ensure df_pulses is not empty before attempting to get unique years
if not df_pulses.empty:
    all_years_for_full_map = sorted(df_pulses["Year"].unique())
else:
    all_years_for_full_map = [] # Set to empty list if df_pulses is empty

for year in all_years_for_full_map:
    # Get state data for the current year
    df_current_year_states = df_pulses[df_pulses["Year"] == year].copy()

    # Create a temporary GeoDataFrame for this year's district data
    temp_gdf_districts_year = gdf_districts.copy()
    temp_gdf_districts_year["Dummy_Value"] = np.nan # Initialize with NaN for districts without data
    temp_gdf_districts_year["Year"] = year # Add the year column for animation

    # Process each state that has data for the current year
    for index, row in df_current_year_states.iterrows():
        state_name_from_data = row["State"]
        state_total_value = row[metric]

        # Normalize state name for matching with district shapefile
        normalized_state_name_data = state_name_from_data.upper().replace(" ", "")

        # Select districts belonging to the current state
        state_districts_mask = temp_gdf_districts_year[state_col].str.upper().str.replace(" ", "") == normalized_state_name_data

        districts_in_state = temp_gdf_districts_year[state_districts_mask][district_col].dropna().unique().tolist()
        n_districts = len(districts_in_state)

        if n_districts > 0 and pd.notna(state_total_value):
            # Fabricate values across districts using random proportions that sum up to the state's total
            proportions = np.random.dirichlet(np.ones(n_districts))
            dummy_values = proportions * state_total_value

            # Assign fabricated values to Dummy_Value column for relevant districts
            for i, district_name in enumerate(districts_in_state):
                temp_gdf_districts_year.loc[
                    (temp_gdf_districts_year[state_col].str.upper().str.replace(" ", "") == normalized_state_name_data) &
                    (temp_gdf_districts_year[district_col] == district_name),
                    "Dummy_Value"
                ] = dummy_values[i]
    animated_full_india_district_data.append(temp_gdf_districts_year)

if animated_full_india_district_data:
    # Concatenate all GeoDataFrames for animation
    animated_full_india_districts_gdf = pd.concat(animated_full_india_district_data, ignore_index=True)

    # Convert the combined GeoDataFrame to GeoJSON for Plotly Express
    full_india_districts_geojson = json.loads(animated_full_india_districts_gdf.to_json())

    # Create the animated full India district map
    fig_full_india_districts = px.choropleth(
        animated_full_india_districts_gdf,
        geojson=full_india_districts_geojson,
        locations=district_col,
        featureidkey=f"properties.{district_col}",
        color="Dummy_Value",
        hover_name=district_col,
        animation_frame="Year",
        color_continuous_scale="YlOrRd",
        title=f"Full India District Map - {metric} ({season}, {pulse_type}) Over Time (Fabricated Values)",
        labels={"Dummy_Value": unit} # Use the same unit as the state map
    )

    # Layout adjustments for the full India district map
    fig_full_india_districts.update_geos(fitbounds="locations", visible=False)
    fig_full_india_districts.update_layout(
        coloraxis_colorbar=dict(title=unit),
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        updatemenus=[{ # Play/Pause buttons
            "type": "buttons",
            "buttons": [
                {
                    "label": "Play",
                    "method": "animate",
                    "args": [None, {
                        "frame": {"duration": 200, "redraw": True},
                        "fromcurrent": True,
                        "transition": {"duration": 0, "easing": "linear"}
                    }]
                },
                {
                    "label": "Pause",
                    "method": "animate",
                    "args": [[None], {
                        "mode": "immediate",
                        "frame": {"duration": 0},
                        "transition": {"duration": 0}
                    }]
                }
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 87},
            "showactive": False,
            "x": 0.1,
            "xanchor": "right",
            "y": 0,
            "yanchor": "top"
        }],
        sliders=[{ # Year slider for full India districts
            "steps": [
                {"args": [[year], {"frame": {"duration": 200, "redraw": True}, "mode": "immediate", "transition": {"duration": 0}}],
                 "label": str(year), "method": "animate"}
                for year in all_years_for_full_map
            ],
            "active": 0,
            "transition": {"duration": 0},
            "x": 0.1,
            "pad": {"b": 10, "t": 50},
            "len": 0.9
        }]
    )
    # Ensure a consistent range for the color axis across all frames
    color_min_full = animated_full_india_districts_gdf["Dummy_Value"].min()
    color_max_full = animated_full_india_districts_gdf["Dummy_Value"].max()
    fig_full_india_districts.update_coloraxes(cmin=color_min_full, cmax=color_max_full)

    st.plotly_chart(fig_full_india_districts, use_container_width=True)
else:
    st.warning("Could not generate animated full India district map. No data available for the selected parameters.")


# ---------- DISTRICT-WISE ANIMATED HISTORICAL PLOT (RANDOM VALUES) ----------
# This section generates a line chart showing simulated historical trends for a selected district.
# This part uses random data and is kept separate from the actual pulse data logic, as requested.
st.markdown("---")
st.subheader("📽️ Animated District-wise Trend (Simulated Data)")

if selected_state_map != "None":
    # Filter districts for the selected state from the main gdf_districts
    filtered_districts_for_line_plot = gdf_districts[
        gdf_districts[state_col].str.upper().str.replace(" ", "") == normalized_selected_state
    ][district_col].dropna().unique().tolist()
    filtered_districts_for_line_plot = sorted(filtered_districts_for_line_plot)
else:
    filtered_districts_for_line_plot = []

if filtered_districts_for_line_plot:
    selected_district_for_line_plot = st.sidebar.selectbox("🎯 Select a District for Trend Animation", filtered_districts_for_line_plot)
else:
    selected_district_for_line_plot = None
    st.sidebar.warning("No districts available for selected state for trend plot.")

if selected_district_for_line_plot:
    # Simulate historical data (e.g., 2000–2023) for the selected district
    years_simulated = np.arange(2000, 2024)
    np.random.seed(42) # For reproducibility of random values
    random_values_simulated = np.random.uniform(low=50, high=300, size=len(years_simulated))

    # Create base dataframe for simulated district trend
    district_trend_simulated_df = pd.DataFrame({
        "Year": years_simulated,
        "Value": random_values_simulated,
        "District": selected_district_for_line_plot
    })

    # Prepare cumulative animation frames for the simulated line plot
    animation_frames_district_line_simulated = []
    for year in years_simulated:
        frame_df = district_trend_simulated_df[district_trend_simulated_df["Year"] <= year].copy()
        frame_df["FrameYear"] = year
        animation_frames_district_line_simulated.append(frame_df)

    animated_district_line_simulated_df = pd.concat(animation_frames_district_line_simulated, ignore_index=True)

    # Axis limits for stable animation
    y_min_simulated = random_values_simulated.min() * 0.95
    y_max_simulated = random_values_simulated.max() * 1.05

    # Create animated plot for simulated district trend
    fig_district_trend_simulated = px.line(
        animated_district_line_simulated_df,
        x="Year",
        y="Value",
        animation_frame="FrameYear",
        animation_group="District",
        title=f"Animated Trend for {selected_district_for_line_plot} (Simulated, {years_simulated.min()}–{years_simulated.max()})",
        markers=True,
        labels={"Year": "Year", "Value": "Simulated Value", "FrameYear": "Year"},
        range_y=[y_min_simulated, y_max_simulated],
        range_x=[years_simulated.min(), years_simulated.max()]
    )

    # Add play/pause buttons for simulated line plot
    fig_district_trend_simulated.update_layout(
        xaxis_title="Year",
        yaxis_title="Simulated Metric",
        font=dict(family="Poppins, sans-serif", size=12),
        title_font_size=18,
        sliders=[{
            'currentvalue': {'prefix': 'Year: '},
            'pad': {'t': 20}
        }],
        updatemenus=[{
            'type': 'buttons',
            'showactive': False,
            'x': 0.05,
            'y': -0.15,
            'buttons': [
                {
                    'label': 'Play',
                    'method': 'animate',
                    'args': [None, {
                        'frame': {'duration': 200, 'redraw': True},
                        'fromcurrent': True,
                        'transition': {'duration': 0}
                    }]
                },
                {
                    'label': 'Pause',
                    'method': 'animate',
                    'args': [[None], {
                        'frame': {'duration': 50, 'redraw': False},
                        'mode': 'immediate',
                        'transition': {'duration': 0}
                    }]
                }
            ]
        }]
    )
    st.plotly_chart(fig_district_trend_simulated, use_container_width=True)
else:
    st.info("Please select a state to view district-wise trend simulation.")
