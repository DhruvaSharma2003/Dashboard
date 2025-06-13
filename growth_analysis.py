import pandas as pd
import numpy as np
from scipy.stats import linregress
import plotly.graph_objects as go

def plot_logest_growth_from_csv(csv_path, category_name, scale_factor=1.0):
    # Load historical data
    df = pd.read_csv(csv_path)

    df["Total"] *= scale_factor

    # Ensure expected format
    df = df[df['Year'].astype(str).str.match(r"^\d{4}$")]
    df['Year'] = df['Year'].astype(int)
    df = df[['Year', 'Total']].dropna()
    df.set_index('Year', inplace=True)

    # Interpolate missing years
    all_years = np.arange(df.index.min(), df.index.max() + 1)
    df = df.reindex(all_years)

    for year in df.index[df['Total'].isnull()]:
        prev_year = max(df.index[df.index < year])
        next_year = min(df.index[df.index > year])
        step = (df.loc[next_year, 'Total'] - df.loc[prev_year, 'Total']) / (next_year - prev_year)
        df.loc[year, 'Total'] = df.loc[prev_year, 'Total'] + step * (year - prev_year)

    # Define decades
    min_decade_start = (df.index.min() // 10) * 10 + 1
    decades = []
    year = min_decade_start
    while year + 9 <= 2020:
        decades.append((year, year + 9))
        year += 10
    if df.index.min() < min_decade_start:
        decades[0] = (df.index.min(), decades[0][1])
    if df.index.max() > 2020:
        decades[-1] = (decades[-1][0], df.index.max())

    # Calculate trend growth rates
    decade_growth_rates = {}
    for start, end in decades:
        mask = (df.index >= start) & (df.index <= end)
        x = np.arange(len(df.loc[mask]))
        y = np.log(df.loc[mask, 'Total'])
        slope, _, _, _, _ = linregress(x, y)
        decade_growth_rates[f"{start}-{end}"] = (np.exp(slope) - 1) * 100

    # Overall growth
    x_all = np.arange(len(df))
    y_all = np.log(df['Total'])
    slope_all, _, _, _, _ = linregress(x_all, y_all)
    overall = (np.exp(slope_all) - 1) * 100

    # Prepare dataframe for plotting
    df_plot = pd.DataFrame({
        "Decade": list(decade_growth_rates.keys()),
        "GrowthRate": list(decade_growth_rates.values())
    })

    # Create Plotly figure with initial empty bars
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_plot["Decade"], y=[0]*len(df_plot), name="Trend Growth Rate"))

    # Create frames → one bar rises at a time
    n_steps_per_bar = 5  # smoothness per bar
    frames = []

    for bar_idx in range(len(df_plot)):
        # Bars before → full height
        # Current bar → rising
        # Bars after → 0
        for step in range(1, n_steps_per_bar+1):
            y_vals = []
            for i in range(len(df_plot)):
                if i < bar_idx:
                    y_vals.append(df_plot["GrowthRate"].iloc[i])
                elif i == bar_idx:
                    y_vals.append(df_plot["GrowthRate"].iloc[i] * (step / n_steps_per_bar))
                else:
                    y_vals.append(0)
            frame = go.Frame(
                data=[go.Bar(x=df_plot["Decade"], y=y_vals)],
                name=f"bar{bar_idx}_step{step}"
            )
            frames.append(frame)

    fig.frames = frames

    # Add overall growth line
    fig.add_hline(y=overall, line_dash="dash", line_color="red", annotation_text=f"Overall Growth Rate ({overall:.2f}%)", annotation_position="top left")

    # Layout with Play button
    fig.update_layout(
        title=f"Decade-wise Trend Growth Rate for {category_name}",
        xaxis_title="Decade Range",
        yaxis_title="Trend Growth Rate (%)",
        yaxis=dict(range=[-2, 10]),
        updatemenus=[{
            "type": "buttons",
            "buttons": [
                {
                    "label": "Play",
                    "method": "animate",
                    "args": [None, {
                        "frame": {"duration": 100, "redraw": True},
                        "fromcurrent": True,
                        "transition": {"duration": 0}
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
            ]
        }],
        margin={"r": 40, "t": 60, "l": 40, "b": 40}
    )

    fig.update_traces(marker_color='lightskyblue')

    return fig
