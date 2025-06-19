import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import time

# --- Configuration ---
st.set_page_config(layout="wide", page_title="India Pulses Data Dashboard", page_icon="🌾")

# --- Constants ---
DATA_DIR = "Data"
GEOJSON_URL = "https://raw.githubusercontent.com/geohacker/india/master/state/india_state.geojson"

# List of all pulse data files (ensure these match your uploaded file names exactly)
PULSE_FILES = [
    "Pulses_Data.xlsx - Arhar.csv",
    "Pulses_Data.xlsx - Gram.csv",
    "Pulses_Data.xlsx - Urad.csv",
    "Pulses_Data.xlsx - Moong.csv",
    "Pulses_Data.xlsx - Masoor.csv",
    "Pulses_Data.xlsx - Moth.csv",
    "Pulses_Data.xlsx - Kulthi.csv",
    "Pulses_Data.xlsx - Khesari.csv",
    "Pulses_Data.xlsx - Peas.csv",
    "Pulses_Data.xlsx - Total Kharif pulses.csv",
    "Pulses_Data.xlsx - Total Rabi pulses.csv",
    "Pulses_Data.xlsx - Total pulses.csv",
    # "Pulses_Data.xlsx - Status.csv" # Exclude status as it doesn't seem to contain pulse data
]

# Mapping for standardizing state names between GeoJSON and your data
# Add more mappings if you encounter discrepancies
STATE_NAME_MAPPING = {
    "Andaman & Nicobar Islands": "A & N Islands",
    "Arunachal Pradesh": "Arunachal Pradesh",
    "Andhra Pradesh": "Andhra Pradesh",
    "Assam": "Assam",
    "Bihar": "Bihar",
    "Chandigarh": "Chandigarh",
    "Chhattisgarh": "Chhattisgarh",
    "Dadra & Nagar Haveli": "Dadra & Nagar Haveli",
    "Daman & Diu": "Daman & Diu",
    "Delhi": "NCT of Delhi",
    "Goa": "Goa",
    "Gujarat": "Gujarat",
    "Haryana": "Haryana",
    "Himachal Pradesh": "Himachal Pradesh",
    "Jammu & Kashmir": "Jammu & Kashmir",
    "Jharkhand": "Jharkhand",
    "Karnataka": "Karnataka",
    "Kerala": "Kerala",
    "Madhya Pradesh": "Madhya Pradesh",
    "Maharashtra": "Maharashtra",
    "Manipur": "Manipur",
    "Meghalaya": "Meghalaya",
    "Mizoram": "Mizoram",
    "Nagaland": "Nagaland",
    "Odisha": "Orissa", # Common discrepancy
    "Puducherry": "Puducherry",
    "Punjab": "Punjab",
    "Rajasthan": "Rajasthan",
    "Sikkim": "Sikkim",
    "Tamil Nadu": "Tamil Nadu",
    "Telangana": "Telangana", # Ensure your data explicitly has Telangana post-bifurcation
    "Tripura": "Tripura",
    "Uttar Pradesh": "Uttar Pradesh",
    "Uttarakhand": "Uttarakhand", # Formerly Uttaranchal
    "West Bengal": "West Bengal",
    "Lakshadweep": "Lakshadweep",
}

# Reverse mapping for GeoJSON names to standardized names if necessary
REVERSE_STATE_NAME_MAPPING = {v: k for k, v in STATE_NAME_MAPPING.items()}


@st.cache_data
def load_data():
    """Loads and preprocesses all pulse data files."""
    all_dfs = []
    for file_name in PULSE_FILES:
        file_path = os.path.join(DATA_DIR, file_name)
        if not os.path.exists(file_path):
            st.error(f"Error: Data file not found at '{file_path}'. Please ensure all CSVs are in the 'data' directory.")
            return pd.DataFrame() # Return empty DataFrame to prevent further errors

        try:
            df = pd.read_csv(file_path)

            # Extract pulse type/season from filename
            pulse_type_season = file_name.replace("Pulses_Data.xlsx - ", "").replace(".csv", "").strip()
            df['Pulse_Type_Season'] = pulse_type_season

            # Rename columns based on user confirmation
            # Prioritize 'State/UT', if not found, try 'States/UTs'
            if 'State/UT' in df.columns:
                df.rename(columns={'State/UT': 'State'}, inplace=True)
            elif 'States/UTs' in df.columns:
                df.rename(columns={'States/UTs': 'State'}, inplace=True)
            else:
                st.warning(f"Could not find 'State/UT' or 'States/UTs' in {file_name}. Check data columns.")
                continue # Skip this file if state column is missing

            # Rename parameter columns
            df.rename(columns={
                'Area (1000 Ha.)': 'Area',
                'Production (1000 Tonnes)': 'Production',
                'Yield (Kg./Ha.)': 'Yield'
            }, inplace=True)

            # Convert relevant columns to numeric, coercing errors
            for col in ['Year', 'Area', 'Production', 'Yield']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            # Drop rows where essential columns are NaN
            df.dropna(subset=['State', 'Year', 'Area', 'Production', 'Yield'], inplace=True)

            # Apply state name mapping for standardization
            df['State'] = df['State'].replace(STATE_NAME_MAPPING)
            all_dfs.append(df)

        except Exception as e:
            st.error(f"Error loading or processing {file_name}: {e}")
            continue

    if not all_dfs:
        return pd.DataFrame()

    combined_df = pd.concat(all_dfs, ignore_index=True)
    return combined_df

@st.cache_data
def load_geojson():
    """Loads the GeoJSON file for India states."""
    try:
        india_states_geojson = px.data.get_geojson(GEOJSON_URL)
        return india_states_geojson
    except Exception as e:
        st.error(f"Error loading GeoJSON: {e}. Please check the URL or your internet connection.")
        return None

# --- Dashboard Layout ---
st.title("🌾 India Pulses Data Dashboard")

# Load data and GeoJSON
df_combined = load_data()
geojson_data = load_geojson()

if df_combined.empty or geojson_data is None:
    st.stop() # Stop execution if data or geojson failed to load

# Ensure 'State' is of type string for merging with geojson properties
df_combined['State'] = df_combined['State'].astype(str)

# Filter out states that are not in the GeoJSON after mapping (optional, for cleaner data)
# First, get unique state names from GeoJSON properties
geojson_state_names = {feature['properties']['ST_NM'] for feature in geojson_data['features']}
# Apply reverse mapping to match the GeoJSON names to our standardized names
standardized_geojson_names = {REVERSE_STATE_NAME_MAPPING.get(name, name) for name in geojson_state_names}

# Filter df_combined to include only states present in GeoJSON
df_combined = df_combined[df_combined['State'].isin(standardized_geojson_names)]


# --- Sidebar Controls ---
st.sidebar.header("Dashboard Controls")

# Select Pulse Type/Season
pulse_types_seasons = sorted(df_combined['Pulse_Type_Season'].unique().tolist())
selected_pulse_type_season = st.sidebar.selectbox(
    "Select Pulse Type / Season:",
    pulse_types_seasons,
    help="Choose the type of pulse data (e.g., Arhar, Total Kharif pulses)."
)

# Filter data based on selected pulse type/season
df_filtered_pulse = df_combined[df_combined['Pulse_Type_Season'] == selected_pulse_type_season]

# Select Parameter
parameters = ['Area', 'Production', 'Yield']
selected_parameter = st.sidebar.selectbox(
    "Select Parameter:",
    parameters,
    help="Choose between Area (1000 Ha.), Production (1000 Tonnes), or Yield (Kg./Ha.)."
)

# Get min and max years for the selected data
min_year = int(df_filtered_pulse['Year'].min()) if not df_filtered_pulse.empty else 1950
max_year = int(df_filtered_pulse['Year'].max()) if not df_filtered_pulse.empty else 2020

# Initialize session state for animation
if 'playing' not in st.session_state:
    st.session_state.playing = False
if 'current_year_idx' not in st.session_state:
    st.session_state.current_year_idx = 0

years = sorted(df_filtered_pulse['Year'].unique().tolist())
if not years:
    st.warning("No data available for the selected pulse type/season.")
    st.stop()

# Animated year slider
st.sidebar.subheader("Year Animation")
col1, col2 = st.sidebar.columns([1, 1])
with col1:
    if st.button("▶️ Play"):
        st.session_state.playing = True
with col2:
    if st.button("⏸️ Pause"):
        st.session_state.playing = False

# Display current year and slider
current_year = years[st.session_state.current_year_idx]
year_slider_value = st.sidebar.slider(
    "Select Year:",
    min_value=min_year,
    max_value=max_year,
    value=current_year,
    step=1,
    key="year_slider"
)

# Update current_year_idx if slider is manually moved
if year_slider_value != current_year:
    st.session_state.current_year_idx = years.index(year_slider_value)
    st.session_state.playing = False # Pause if user manually changes slider

st.sidebar.markdown(f"**Current Year: {year_slider_value}**")

# Animation loop (only runs if playing is True)
if st.session_state.playing:
    # Use st.empty to update the slider and map in place
    placeholder = st.empty()
    with placeholder:
        while st.session_state.playing and st.session_state.current_year_idx < len(years):
            st.session_state.current_year_idx = (st.session_state.current_year_idx % len(years))
            current_animated_year = years[st.session_state.current_year_idx]

            # Re-run the app to update the map with the new year
            st.sidebar.slider(
                "Select Year:",
                min_value=min_year,
                max_value=max_year,
                value=current_animated_year,
                step=1,
                key="year_slider_animated" # Use a different key for animation
            )
            st.sidebar.markdown(f"**Current Year: {current_animated_year}**")

            # Filter data for the current animated year
            df_year = df_filtered_pulse[df_filtered_pulse['Year'] == current_animated_year]

            # Create the choropleth map
            if not df_year.empty and geojson_data:
                fig = px.choropleth(
                    df_year,
                    geojson=geojson_data,
                    featureidkey="properties.ST_NM", # Key in GeoJSON that matches 'State' column
                    locations="State",
                    color=selected_parameter,
                    hover_name="State",
                    hover_data={
                        "State": True,
                        selected_parameter: ':,2f', # Format parameter to 2 decimal places
                        "Year": True
                    },
                    color_continuous_scale="Viridis",
                    title=f'{selected_pulse_type_season} - {selected_parameter} in {current_animated_year}',
                    projection="mercator",
                    height=600
                )
                fig.update_geos(fitbounds="locations", visible=False)
                fig.update_layout(margin={"r":0,"t":50,"l":0,"b":0})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No data to display for {selected_pulse_type_season} in {current_animated_year}.")

            time.sleep(0.8) # Animation speed
            st.session_state.current_year_idx += 1

            # Loop back to start if end is reached
            if st.session_state.current_year_idx >= len(years):
                st.session_state.current_year_idx = 0 # Loop back to the first year


# Display the map based on the current selected year (either manual or paused animation)
if not st.session_state.playing:
    df_year = df_filtered_pulse[df_filtered_pulse['Year'] == year_slider_value]

    if not df_year.empty and geojson_data:
        fig = px.choropleth(
            df_year,
            geojson=geojson_data,
            featureidkey="properties.ST_NM", # Key in GeoJSON that matches 'State' column
            locations="State",
            color=selected_parameter,
            hover_name="State",
            hover_data={
                "State": True,
                selected_parameter: ':,2f',
                "Year": True
            },
            color_continuous_scale="Viridis",
            title=f'{selected_pulse_type_season} - {selected_parameter} in {year_slider_value}',
            projection="mercator",
            height=600
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(margin={"r":0,"t":50,"l":0,"b":0})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"No data to display for {selected_pulse_type_season} in {year_slider_value}.")
