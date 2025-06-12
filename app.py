import streamlit as st
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
from growth_analysis import plot_logest_growth_from_csv
from world_map import show_world_timelapse_map
import glob
import json
import numpy as np 
import geopandas as gpd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium
import matplotlib.cm as cm
import matplotlib.colors as colors
from folium.plugins import TimestampedGeoJson
from streamlit.components.v1 import html


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

# ---------- SIDEBAR DROPDOWN ----------
selected_type_sidebar = st.sidebar.selectbox(
    "Select Type:",
    ["Production", "Yield", "Area"],
    index=0 if st.session_state.selected_type is None else ["Production", "Yield", "Area"].index(st.session_state.selected_type)
)

# Update session state if changed
if selected_type_sidebar != st.session_state.selected_type:
    st.session_state.selected_type = selected_type_sidebar

# ---------- INFO / STOP IF NONE SELECTED ----------
selected_type = st.session_state.selected_type
if not selected_type:
    st.markdown("<h4 style='text-align:center;'>Please select <b>Production</b>, <b>Yield</b>, or <b>Area</b> to continue.</h4>", unsafe_allow_html=True)
    st.stop()

# ---------- UNIT LOOKUP ----------
unit_lookup = {
    "Yield": {
        "Oilseeds": "Kg./hectare", "Pulses": "Kg./hectare", "Rice": "Kg./hectare", "Wheat": "Kg./hectare",
        "Coarse Cereals": "Kg./hectare", "Maize": "Kg./hectare", "Fruits": "MT/hectare", "Vegetables": "MT/hectare"
    },
    "Production": {
        "Milk": "Million Tonne", "Meat": "Million Tonne", "Eggs": "Million Numbers", "Sugar and Products": "Lakh Tonne",
        "Fruits": "'000 MT", "Vegetables": "'000 MT", "Foodgrains": "'000 Tonne", "Cereals": "'000 Tonne",
        "Pulses": "'000 Tonne", "Rice": "'000 Tonne", "Wheat": "'000 Tonne", "Coarse Cereals": "'000 Tonne", "Maize": "'000 Tonne"
    },
    "Area": {
        "Foodgrains": "Lakh hectare", "Cereals": "'000 hectare", "Fruits": "'000 hectare", "Oilseeds": "'000 hectare",
        "Pulses": "'000 hectare", "Rice": "'000 hectare", "Vegetables": "'000 hectare", "Wheat": "'000 hectare",
        "Coarse Cereals": "'000 hectare", "Maize": "'000 hectare"
    }
}
unit_conversion_map = {
    "'000 Tonne": {"Million Tonne": 0.001}, "'000 MT": {"Million Tonne": 0.001},
    "'000 hectare": {"Million hectare": 0.001}, "Lakh hectare": {"Million hectare": 0.1},
    "Million Numbers": {"Billion Numbers": 0.001}, "Kg./hectare": {"Tonne/hectare": 0.001}
}

# ---------- HEADER ----------
st.markdown(f"<h1 style='text-align:center;'>🌾 India FoodCrop Data Dashboard</h1>", unsafe_allow_html=True)

# ---------- PATH & PREFIX ----------
prefix_map = {"Production": "prod_", "Yield": "yield_", "Area": "area_"}
prefix = prefix_map[selected_type]
base_path = f"Data/{selected_type}"

# ---------- FOLDERS ----------
available_folders = [f.replace(prefix, "") for f in os.listdir(base_path) if f.startswith(prefix)]

# ---------- CATEGORY HIERARCHY ----------
category_hierarchy = {
    "Agriculture": {
        "Foodgrains": {
            "Cereals": ["Rice", "Wheat", "Cereals"],
            "Foodgrains": ["Foodgrains"],
            "Coarse Cereals": ["Maize", "Coarse Cereals"],
            "Pulses": ["Pulses"]
        },
        "Horticulture": {"Fruits": ["Fruits"], "Vegetables": ["Vegetables"]},
        "Oilseeds": {"Oilseeds": ["Oilseeds"]},
        "Commercial Crops": {"Sugar and Products": ["Sugar and Products"]}
    },
    "Allied Sectors": {
        "Animal Products": {
            "Eggs": ["Eggs"], "Milk": ["Milk"], "Meat": ["Meat"], "Marine and Inland Fish": ["Marine and Inland Fish"]
        }
    }
}

# ---------- SIDEBAR CATEGORY PICKER ----------
with st.sidebar:
    st.markdown(f"<div class='sidebar-title'>{selected_type} Categories</div>", unsafe_allow_html=True)
    sector = st.selectbox("Main Sector", list(category_hierarchy.keys()))
    sub_sector = st.selectbox("Sub-Sector", list(category_hierarchy[sector].keys()))

    def normalize(name): return name.lower().replace(" ", "").replace("_", "")
    subcat_display_to_folder = {}
    norm_available = {normalize(f): f for f in available_folders}

    for subcat_list in category_hierarchy[sector][sub_sector].values():
        for subcat in subcat_list:
            norm_subcat = normalize(subcat)
            if norm_subcat in norm_available:
                subcat_display_to_folder[subcat] = norm_available[norm_subcat]

    if not subcat_display_to_folder:
        st.error("No data available for selected sub-sector.")
        st.stop()

    category = st.selectbox("Category", list(subcat_display_to_folder.keys()))
    folder_key = subcat_display_to_folder[category]
    folder_name = f"{prefix}{folder_key}"
    folder_path = os.path.join(base_path, folder_name)

# ---------- UNIT CONVERSION PICKER ----------
unit = unit_lookup.get(selected_type, {}).get(category, "")
conversion_options = unit_conversion_map.get(unit, {})
conversion_multiplier = 1.0
if conversion_options:
    chosen_unit = st.sidebar.selectbox("Convert Unit", ["Original"] + list(conversion_options.keys()))
    if chosen_unit != "Original":
        conversion_multiplier = conversion_options[chosen_unit]
        unit = chosen_unit
# ---------- SAFE READ ----------
def safe_read(filename):
    full_path = os.path.join(folder_path, filename)
    return pd.read_csv(full_path) if os.path.exists(full_path) else None

historical_df = safe_read("historical_data.csv")
forecast_df = safe_read("forecast_data.csv")
wg_df = safe_read("wg_report.csv")

# ---------- Apply conversion ----------
if historical_df is not None:
    historical_df["Total"] *= conversion_multiplier

if forecast_df is not None:
    forecast_df.iloc[:, 1:] *= conversion_multiplier

if wg_df is not None and not wg_df.empty:
    wg_df["Value"] *= conversion_multiplier

# ---------- WORLD MAP ----------
with st.sidebar:    
    st.markdown("### 🌍 World View Map")
    base_world_path = os.path.join("world data", selected_type)
    file_list = glob.glob(os.path.join(base_world_path, "*.csv"))
    available_categories = {
        os.path.basename(f)
        .replace("prod_", "")
        .replace("yield_", "")
        .replace("area_", "")
        .replace("_country.csv", "")
        .replace("_", " ")
        .title(): f
        for f in file_list
    }

    selected_file = None
    selected_world_category = None
    if available_categories:
        selected_world_category = st.selectbox("World Map Category", list(available_categories.keys()))
        selected_file = available_categories[selected_world_category]

# ---------- MAIN WORLD RENDER ----------

if selected_file:
    df_world = pd.read_csv(selected_file)
    st.markdown("---")
    st.subheader(f"🌐 {selected_world_category} {selected_type} Over Time")
    show_world_timelapse_map(df_world, metric_title=f"{selected_world_category} {selected_type}")
elif selected_type:  # Only warn if type was selected but no files
    st.warning("No data files found for selected type.")

# ---------- FORECAST TIMELINE ----------
st.markdown("---")
st.subheader("📊 Future Projections for top 3 Models")
if historical_df is not None and forecast_df is not None:
    # Prepare historical data
    historical_df = historical_df.rename(columns={"Total": "Value"})
    historical_df["Model"] = "Historical"

    # Prepare forecast data
    forecast_long_df = forecast_df.melt(id_vars="Year", var_name="Model", value_name="Value")

    # Combine all data
    combined_df = pd.concat([historical_df, forecast_long_df], ignore_index=True)
    combined_df = combined_df.sort_values(by=["Model", "Year"])

    # --- (KEY CHANGE) Define all models and animation years upfront ---
    all_model_names = ["Historical"] + forecast_df.columns[1:].tolist()
    all_animation_years = sorted(combined_df["Year"].unique())

    # --- Build the frames with placeholder data to ensure continuity ---
    timeline_frames = []
    for year in all_animation_years:
        # Get all data up to the current animation year
        frame_data = combined_df[combined_df["Year"] <= year].copy()
        frame_data["FrameYear"] = year

        # --- (KEY CHANGE) The robust fix:
        # Ensure a row exists for every model in this frame. If a model has no data yet,
        # add a placeholder with a null value so Plotly knows it exists.
        present_models = frame_data["Model"].unique()
        missing_models = set(all_model_names) - set(present_models)

        if missing_models:
            placeholders = []
            for model in missing_models:
                # Use the first historical year as a non-plotting anchor
                placeholders.append({
                    "Year": historical_df["Year"].min(),
                    "Model": model,
                    "Value": np.nan, # Use np.nan for a gap in the line
                    "FrameYear": year
                })
            frame_data = pd.concat([frame_data, pd.DataFrame(placeholders)], ignore_index=True)

        timeline_frames.append(frame_data)

    timeline_df = pd.concat(timeline_frames, ignore_index=True)

    # --- AXIS BOUNDS ---
    full_data_range = pd.concat([
        combined_df["Value"],
        wg_df["Value"] if wg_df is not None and not wg_df.empty else pd.Series(dtype='float64')
    ])
    y_min = full_data_range.min() * 0.95
    y_max = full_data_range.max() * 1.05
    x_min = historical_df["Year"].min()
    x_max = max(forecast_df["Year"].max(), 2047) if not forecast_df.empty else 2047

    # --- PLOT THE ANIMATED LINE CHART ---
    # The category_orders is still good practice to control the legend order.
    fig_timeline = px.line(
        timeline_df,
        x="Year",
        y="Value",
        color="Model",
        animation_frame="FrameYear",
        animation_group="Model",
        title=f"📊 Historical Data and Future Projections ({unit})",
        markers=True,
        range_y=[y_min, y_max],
        range_x=[x_min, x_max],
        category_orders={"Model": all_model_names}
    )

    # --- ADD THE STATIC WG REPORT POINTS ---
    if wg_df is not None and not wg_df.empty:
        fig_timeline.add_trace(go.Scatter(
            x=wg_df["Year"],
            y=wg_df["Value"],
            mode="markers+text",
            name="WG Report",
            marker=dict(color="red", size=12, symbol="diamond"),
            text=wg_df["Scenario"],
            textposition="top right",
            showlegend=True
        ))

    # --- CUSTOMIZE LAYOUT AND AESTHETICS ---
    fig_timeline.update_layout(
        updatemenus=[{
            "type": "buttons",
            "buttons": [{
                "label": "Play",
                "method": "animate",
                "args": [None, {
                    "frame": {"duration": 10, "redraw": True},  # Lower = faster (ms)
                    "fromcurrent": True,
                    "transition": {"duration": 1, "easing": "linear"}
                }]
            }, {
                "label": "Pause",
                "method": "animate",
                "args": [[None], {
                    "mode": "immediate",
                    "frame": {"duration": 0},
                    "transition": {"duration": 0}
                }]
            }]
        }]
    )    

    fig_timeline.update_layout(
        yaxis_title=f"Value ({unit})",
        xaxis_title="Year",
        legend_title="Model/Scenario",
        font=dict(family="Poppins, sans-serif", size=12),
        title_font_size=22,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    fig_timeline.update_layout({
        'sliders': [{'currentvalue': {'prefix': 'Year: '},'pad': {'t': 20}}]
    })

    st.plotly_chart(fig_timeline, use_container_width=True)

# ---------- LOGEST GROWTH ----------
st.markdown("---")
st.subheader("📈 Decade-wise Trend Growth Rate")
csv_path = os.path.join(folder_path, "historical_data.csv")
if os.path.exists(csv_path):
    fig = plot_logest_growth_from_csv(csv_path, category, conversion_multiplier)
    st.pyplot(fig)

# ---------- INDIA PULSES CHOROPLETH MAP ----------
'''
st.markdown("---")
st.subheader("🇮🇳 India Pulses Choropleth Map Over Time")

with st.sidebar:
    st.markdown("---")
    st.markdown("### 🌱 Pulses Map Settings")
    season = st.selectbox("Select Season", ["Kharif", "Rabi", "Total"])

    pulse_sheets = ["Gram", "Urad", "Moong", "Masoor", "Moth", "Kulthi", "Khesari", "Peas", "Arhar"]
    pulse_type = st.selectbox("Select Pulse Type", pulse_sheets)

    metric = st.selectbox("Select Metric", ["Area", "Production", "Yield"])

try:
    
    df = pd.read_excel(
        "Data/Pulses_Data.xlsx",
        sheet_name=pulse_type,
        header=1  # Header is in second row (row 2 in Excel)
    )

    # Remove any extra spaces in column names (important!!)
    df.columns = df.columns.str.strip()

    # Rename "States/UTs" → "State"
    df = df.rename(columns={"States/UTs": "State"})

    # Filter season-wise
    df = df[df["Season"].str.lower() == season.lower()]

    # Coerce numeric
    df["Year"] = df["Year"].astype(str)
    df[metric] = pd.to_numeric(df[metric], errors="coerce")
    df = df.dropna(subset=[metric])

    df["State"] = df["State"].str.strip()
    df["State"] = df["State"].replace({
        "Orissa": "Odisha",
        "Jammu & Kashmir": "Jammu and Kashmir",
        "Chhattisgarh": "Chhattishgarh",
        "Telangana": "Telengana",
        "Tamil Nadu": "Tamilnadu",
        "Kerela": "Kerala",
        "Andaman & Nicobar Islands": "Andaman & Nicobar"
    
    })

    selected_year = st.sidebar.selectbox("Select Year", sorted(df["Year"].unique()))

    df_selected_year = df[df["Year"] == selected_year]

    # Load shapefile
    gdf = gpd.read_file("India_Shapefile/india_st.shp")

    # Clean columns → very important!
    df_selected_year["State"] = df_selected_year["State"].str.strip().str.upper()
    gdf["STNAME"] = gdf["STNAME"].str.strip().str.upper()

    # Optional → map common name mismatches
    df_selected_year["State"] = df_selected_year["State"].replace({
        "Orissa": "Odisha",
        "Jammu & Kashmir": "Jammu and Kashmir",
        "Chhattisgarh": "Chhattishgarh",
        "Telangana": "Telengana",
        "Tamil Nadu": "Tamilnadu",
        "Kerela": "Kerala",
        "Andaman & Nicobar Islands": "Andaman & Nicobar"
        
    })

    # Merge Shapefile with selected year df
    merged = gdf.merge(df_selected_year, left_on="STNAME", right_on="State", how="left")

    # Plot India map
    fig, ax = plt.subplots(1, 1, figsize=(10, 12))
    merged.plot(
        column=metric,
        ax=ax,
        legend=True,
        cmap='YlOrRd',
        edgecolor='black',
        missing_kwds={"color": "white", "edgecolor": "black"}
    )

    plt.title(f"{pulse_type} - {season} - {metric} in {selected_year}")
    st.pyplot(fig)

except Exception as e:
    st.error(f"An error occurred: {e}")
'''
from matplotlib import colormaps  # New API in matplotlib >=3.7

def get_color(value, vmin, vmax):
    norm = colors.Normalize(vmin=vmin, vmax=vmax)
    cmap = colormaps['YlOrRd']
    rgba = cmap(norm(value))
    return colors.to_hex(rgba)

# ---------- INDIA MAP VIEW ----------

st.markdown("---")
st.subheader("🇮🇳 India Pulses Choropleth Map Over Time")

with st.sidebar:
    st.markdown("---")
    st.markdown("### 🌱 Pulses Map Settings")
    season = st.selectbox("Select Season", ["Kharif", "Rabi", "Total"])
    pulse_sheets = ["Gram", "Urad", "Moong", "Masoor", "Moth", "Kulthi", "Khesari", "Peas", "Arhar"]
    pulse_type = st.selectbox("Select Pulse Type", pulse_sheets)
    metric = st.selectbox("Select Metric", ["Area", "Production", "Yield"])


try:
    import json
    import matplotlib.cm as cm
    import matplotlib.colors as colors
    from folium.plugins import TimestampedGeoJson

    # Read data
    df = pd.read_excel(
        "Data/Pulses_Data.xlsx",
        sheet_name=pulse_type,
        header=1
    )

    # Clean and prepare data
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"States/UTs": "State"})
    df = df[df["Season"].str.lower() == season.lower()]
    df["Year"] = df["Year"].astype(str)
    df[metric] = pd.to_numeric(df[metric], errors="coerce")
    df = df.dropna(subset=[metric])
    df["State"] = df["State"].str.strip().str.upper()

    df["State"] = df["State"].replace({
        "ORISSA": "ODISHA",
        "JAMMU & KASHMIR": "JAMMU & KASHMIR",
        "CHHATTISGARH": "CHHATTISGARH",
        "TELANGANA": "TELANGANA",
        "TAMIL NADU": "TAMIL NADU",
        "KERELA": "KERALA",
        "ANDAMAN & NICOBAR ISLANDS": "ANDAMAN & NICOBAR"
    })

    # Load geojson
    gdf_states = gpd.read_file("India_Shapefile/INDIA_STATES.geojson")
    gdf_states["STNAME"] = gdf_states["STNAME"].str.strip().str.upper()

    # Create folium map
    m = folium.Map(location=[22.9734, 78.6569], zoom_start=5, tiles="CartoDB positron")

    # Build timestamped features
    features = []
    
    # Normalize color scale
    vmin, vmax = df[metric].min(), df[metric].max()

    for year in sorted(df["Year"].unique()):
        df_year = df[df["Year"] == year]
        state_metric_map = dict(zip(df_year["State"], df_year[metric]))

        for _, row in gdf_states.iterrows():
            STNAME = row["STNAME"]
            value = state_metric_map.get(STNAME, None)
            # Example use of the color function
            fill_color = get_color(value, vmin, vmax) if value is not None else "#eeeeee"


            feature = {
                "type": "Feature",
                "geometry": row["geometry"].__geo_interface__,
                "properties": {
                    "time": f"{year}-01-01",
                    "style": {
                        "color": "black",
                        "weight": 0.3,
                        "fillColor": fill_color,
                        "fillOpacity": 0.6
                    },
                    "popup": f"{STNAME}<br>{metric}: {value:.2f}" if value is not None else f"{STNAME}<br>{metric}: N/A"
                }
            }

            features.append(feature)

    # Add animated layer
    TimestampedGeoJson({
        "type": "FeatureCollection",
        "features": features
    }, 
        period="P1Y",
        add_last_point=True,
        transition_time=500,
        auto_play=False,
        loop=False,
        max_speed=1,
        loop_button=True,
        date_options="YYYY",
        time_slider_drag_update=True
    ).add_to(m)

    # Display in Streamlit
    try:
        html(m._repr_html_(), height=700)
    except Exception as e:
        st.error("Map rendering failed.")
        st.exception(e)
except Exception as e:
    st.error(f"An error occurred: {e}")


# ---------- STATE MAP VIEW ----------
'''
# Load full India District shapefile (load once → top of file / cache)
@st.cache_data
def load_india_districts_shapefile():
    gdf = gpd.read_file("India_Shapefile/State/2011_Dist.shp")
    gdf = gdf.set_crs(epsg=4326, inplace=False)
    return gdf

STNAME_CORRECTIONS = {
    "Orissa": "Odisha",
    "Jammu & Kashmir": "Jammu and Kashmir",
    "Chhattisgarh": "Chhattishgarh",
    "Telangana": "Telengana",
    "Tamil Nadu": "Tamilnadu",
    "Kerela": "Kerala",
    "Andaman & Nicobar Islands": "Andaman & Nicobar",
    "Arunachal Pradesh": "Arunanchal Pradesh",
    "Dadra & Nagar Haveli": "Dadara & Nagar Havelli",
    "India": None,  # Special handling → we don't want user to select "India" in district map!
    "Delhi": "NCT of Delhi"
}


gdf_districts = load_india_districts_shapefile()
gdf_districts["ST_NM"] = gdf_districts["ST_NM"].replace(STNAME_CORRECTIONS)
gdf_districts["ST_NM"] = gdf_districts["ST_NM"].str.strip().str.upper()

# Sidebar: State Map View
st.sidebar.markdown("---")
st.sidebar.markdown("### 🗺️ State Map View")

# Dynamic State Map View dropdown

# Extract available states in current df_selected_year
available_states = df_selected_year["State"].str.upper().unique().tolist()

# Dropdown options → dynamic + "None" on top
state_options = ["None"] + sorted(available_states)

selected_state_map = st.sidebar.selectbox("Select State for State Map", state_options)

# Auto detect STATE column
state_col = None
for col in gdf_districts.columns:
    if "STATE" in col.upper() or "ST_NM" in col.upper():
        state_col = col
        break

# Auto detect DISTRICT column
district_col = None
for col in gdf_districts.columns:
    if "DISTRICT" in col.upper() or "DIST_NAME" in col.upper() or "DIST_NM" in col.upper():
        district_col = col
        break

# Debug: show all unique state names from district shapefile
#st.write("States in shapefile (after replacement and uppercasing):")
#st.write(sorted(gdf_districts[state_col].unique().tolist()))

#st.write("States in Pulses DataFrame (df_selected_year):")
#st.write(sorted(df_selected_year["State"].str.upper().unique().tolist()))


# Proceed only if valid state selected
if selected_state_map != "None":

    # Safety check
    if state_col is None or district_col is None:
        st.error("Could not detect STATE or DISTRICT column in shapefile!")
    else:
        # Normalize function: remove spaces, convert to upper
        def normalize_STNAME(s):
            return s.upper().replace(" ", "")

        # Filter for selected state safely
        state_gdf = gdf_districts[gdf_districts[state_col].apply(normalize_STNAME) == normalize_STNAME(selected_state_map)]


        # Optional: explode in case MultiPolygon present
        state_gdf = state_gdf.explode(index_parts=False)

        # Prepare df_selected_year → selected state row
        state_row = df_selected_year[df_selected_year["State"].str.upper() == selected_state_map.upper()]

        if state_row.empty:
            st.warning(f"No data available for {selected_state_map} for {season} - {pulse_type} - {metric} in selected year.")
        else:
            # Extract actual state value
            state_total_value = state_row[metric].values[0]

            # Prepare dummy values per district
            districts = state_gdf[district_col].tolist()
            n_districts = len(districts)

            # Random proportions summing to 1
            proportions = np.random.dirichlet(np.ones(n_districts))
            dummy_values = proportions * state_total_value

            # Assign dummy values to GeoDataFrame
            state_gdf["Dummy_Value"] = dummy_values
            state_gdf["District"] = state_gdf[district_col]

            # Plot State district map
            st.markdown(f"### 📍 {selected_state_map} District Map - {metric} ({season}, {pulse_type})")

            fig2, ax2 = plt.subplots(1, 1, figsize=(8, 10))
            state_gdf.plot(
                column="Dummy_Value",
                ax=ax2,
                legend=True,
                cmap='YlOrRd',
                edgecolor='black',
                missing_kwds={"color": "white", "edgecolor": "black"}
            )
            plt.title(f"{selected_state_map} District Map - {metric} ({season}, {pulse_type})", fontsize=14)

            # Plot district names only once per district
            unique_districts = state_gdf.drop_duplicates(subset="District")

            for idx, row in unique_districts.iterrows():
                centroid = row["geometry"].centroid
                ax2.text(centroid.x, centroid.y, row["District"], fontsize=8, ha='center')

            st.pyplot(fig2)

            # ---------- STATE-WISE ANIMATED HISTORICAL PLOT ----------
            if not state_row.empty:
                #st.markdown("---")
                st.markdown(f"### Animated Historical Trend for {selected_state_map}")

                #
                # Filter the main dataframe for the selected state across ALL available years
                state_historical_df = df[df["State"].str.upper() == selected_state_map.upper()].copy()
                state_historical_df['Year'] = pd.to_numeric(state_historical_df['Year'].astype(str).str.split('-').str[0]) # <--- USE THIS NEW LINE
                state_historical_df = state_historical_df.sort_values("Year")
                #

                # Define units for the pulse metrics for clearer axis labels
                pulse_units = {
                    "Area": "'000 Hectare",
                    "Production": "'000 Tonne",
                    "Yield": "Kg/Hectare"
                }
                y_axis_title = f"{metric} ({pulse_units.get(metric, '')})"

                # Proceed only if there's data to animate
                if not state_historical_df.empty and state_historical_df[metric].notna().any():
                    
                    # --- Prepare data for animation ---
                    # This creates a cumulative dataset for each year, which is necessary for the animation.
                    all_years = sorted(state_historical_df["Year"].unique())
                    animation_frames = []

                    for year in all_years:
                        frame_data = state_historical_df[state_historical_df["Year"] <= year].copy()
                        frame_data["FrameYear"] = year  # This column drives the animation
                        animation_frames.append(frame_data)
                    
                    animated_state_df = pd.concat(animation_frames, ignore_index=True)

                    # --- Define axis bounds for a stable animation view ---
                    y_min_state = state_historical_df[metric].min() * 0.95
                    y_max_state = state_historical_df[metric].max() * 1.05
                    x_min_state = state_historical_df["Year"].min()
                    x_max_state = state_historical_df["Year"].max()

                    # --- Create the animated line plot ---
                    fig_state_trend = px.line(
                        animated_state_df,
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

                    # --- Customize Layout and Animation Controls ---
                    fig_state_trend.update_layout(
                        yaxis_title=y_axis_title,
                        xaxis_title="Year",
                        font=dict(family="Poppins, sans-serif", size=12),
                        title_font_size=18,
                        legend_title="Metric",
                        sliders=[{
                            'currentvalue': {'prefix': 'Year: '},
                            'pad': {'t': 20}
                        }],
                        updatemenus=[{
                            'type': 'buttons',
                            'showactive': False,
                            'x': 0.05,
                            'y': -0.15,
                            'buttons': [{
                                'label': 'Play',
                                'method': 'animate',
                                'args': [None, {
                                    'frame': {'duration': 10, 'redraw': True},  # << faster animation (300 ms per frame)
                                    'fromcurrent': True,
                                    'transition': {'duration': 1}
                                }]
                            }, {
                            'label': 'Pause',
                            'method': 'animate',
                            'args': [[None], {
                                'frame': {'duration': 0, 'redraw': False},
                                'mode': 'immediate',
                                'transition': {'duration': 0}
                            }]
                            }]
                        }]
                    )
                    
                    # Customize the appearance of the animation slider
                    fig_state_trend.update_layout({
                        'sliders': [{'currentvalue': {'prefix': 'Year: '}, 'pad': {'t': 20}}]
                    })

                    st.plotly_chart(fig_state_trend, use_container_width=True)
                else:
                    st.warning(f"No historical data with values for '{metric}' is available to plot a trend for {selected_state_map}.")





# ---------- FULL INDIA DISTRICT MAP ----------
st.markdown("---")
st.subheader("🇮🇳 Full India District Map View (Fabricated Values)")

# Auto detect STATE and DISTRICT columns
state_col = None
district_col = None
for col in gdf_districts.columns:
    if "STATE" in col.upper() or "ST_NM" in col.upper():
        state_col = col
    if "DISTRICT" in col.upper() or "DIST_NAME" in col.upper() or "DIST_NM" in col.upper():
        district_col = col

# Check
if state_col is None or district_col is None:
    st.error("Could not detect STATE or DISTRICT column in shapefile!")
else:
    # Prepare a copy of gdf_districts to avoid inplace modification
    gdf_districts_full = gdf_districts.copy()

    # Prepare Dummy_Value column
    gdf_districts_full["Dummy_Value"] = 0.0

    # Process each state in df_selected_year
    for STNAME in df_selected_year["State"].unique():
        STNAME_upper = STNAME.strip().upper()

        # Match in shapefile with normalization
        def normalize_STNAME(s):
            return s.upper().replace(" ", "")

        mask = gdf_districts_full[state_col].apply(normalize_STNAME) == normalize_STNAME(STNAME_upper)
        state_gdf = gdf_districts_full[mask]

        # If no matching districts → skip
        if state_gdf.empty:
            continue

        # Get state total value from df_selected_year
        state_row = df_selected_year[df_selected_year["State"].str.upper() == STNAME_upper]
        if state_row.empty:
            continue

        state_total_value = state_row[metric].values[0]

        # Fabricate values across districts
        districts = state_gdf[district_col].unique().tolist()
        n_districts = len(districts)

        proportions = np.random.dirichlet(np.ones(n_districts))
        dummy_values = proportions * state_total_value

        # Assign fabricated values to Dummy_Value column
        for i, district_name in enumerate(districts):
            gdf_districts_full.loc[
                (mask) & (gdf_districts_full[district_col] == district_name),
                "Dummy_Value"
            ] = dummy_values[i]

    # Plot the full India district map
    fig_full, ax_full = plt.subplots(1, 1, figsize=(12, 14))
    gdf_districts_full.plot(
        column="Dummy_Value",
        ax=ax_full,
        legend=True,
        cmap='YlOrRd',
        edgecolor='black',
        missing_kwds={"color": "white", "edgecolor": "black"}
    )
    ax_full.set_title(f"Full India District Map - {metric} ({season}, {pulse_type}, {selected_year})", fontsize=16)

    st.pyplot(fig_full)

# ---------- DISTRICT-WISE ANIMATED HISTORICAL PLOT (RANDOM VALUES) ----------
st.markdown("---")
st.subheader("📽️ Animated District-wise Trend (Simulated Data)")

all_districts = sorted(gdf_districts_full[district_col].dropna().unique().tolist())

# Sidebar dropdown to select a district
selected_district = st.sidebar.selectbox("🎯 Select a District for Trend Animation", all_districts)

# Simulate historical data (e.g., 2000–2023)
years = np.arange(2000, 2024)
random_values = np.random.uniform(low=50, high=300, size=len(years))

# Create base dataframe
district_trend_df = pd.DataFrame({
    "Year": years,
    "Value": random_values,
    "District": selected_district
})

# Prepare cumulative animation frames
animation_frames = []
for year in years:
    frame_df = district_trend_df[district_trend_df["Year"] <= year].copy()
    frame_df["FrameYear"] = year
    animation_frames.append(frame_df)

animated_district_df = pd.concat(animation_frames, ignore_index=True)

# Axis limits for stable animation
y_min = random_values.min() * 0.95
y_max = random_values.max() * 1.05

# Create animated plot
fig_district_trend = px.line(
    animated_district_df,
    x="Year",
    y="Value",
    animation_frame="FrameYear",
    animation_group="District",
    title=f"Animated Trend for {selected_district} (Simulated, 2000–2023)",
    markers=True,
    labels={"Year": "Year", "Value": "Simulated Value", "FrameYear": "Year"},
    range_y=[y_min, y_max],
    range_x=[years.min(), years.max()]
)

# Add play/pause buttons
fig_district_trend.update_layout(
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
                    'transition': {'duration': 100}
                }]
            },
            {
                'label': 'Pause',
                'method': 'animate',
                'args': [[None], {
                    'frame': {'duration': 0, 'redraw': False},
                    'mode': 'immediate',
                    'transition': {'duration': 0}
                }]
            }
        ]
    }]
)

st.plotly_chart(fig_district_trend, use_container_width=True)

def show_india_timelapse_map(df, geojson_path, metric_title="Production", default_unit="Tonnes"):
    # Load GeoJSON file
    with open(geojson_path, "r") as f:
        india_states_geojson = json.load(f)

    # Determine unit
    unit = df["Unit"].iloc[0] if "Unit" in df.columns and not df["Unit"].isna().all() else default_unit
    title = f"{metric_title} Over Time ({unit})"

    # Create choropleth
    fig = px.choropleth(
        df,
        geojson=india_states_geojson,
        locations="State",                        # Your CSV column name
        featureidkey="properties.STNAME",         # Your GeoJSON property
        color="Value",
        hover_name="State",
        animation_frame="Year",
        color_continuous_scale="YlGnBu",
        title=title
    )

    # Layout tweaks
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        coloraxis_colorbar=dict(title=unit),
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        updatemenus=[{
            "type": "buttons",
            "buttons": [ 
                {
                    "label": "Play",
                    "method": "animate",
                    "args": [None, {
                        "frame": {"duration": 100, "redraw": True},
                        "fromcurrent": True,
                        "transition": {"duration": 1, "easing": "linear"}
                    }]
                },
                {
                    "label": "Pause",
                    "method": "animate",
                    "args": [[None], {
                        "mode": "immediate",
                        "frame": {"duration": 0},
                        "transition": {"duration": 10}
                    }]
                }
            ]
        }]
    )

    st.plotly_chart(fig, use_container_width=True)
'''








