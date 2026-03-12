import streamlit as st
import pandas as pd
import pyarrow.parquet as pq
import os
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image

st.set_page_config(layout="wide")

st.title("LILA Player Journey Visualization Tool")

DATA_PATH = "player_data"

# -----------------------------
# MAP CONFIG
# -----------------------------

MAP_CONFIG = {
    "AmbroseValley": {
        "scale": 900,
        "origin_x": -370,
        "origin_z": -473,
        "image": "player_data/minimaps/AmbroseValley_Minimap.png"
    },
    "GrandRift": {
        "scale": 581,
        "origin_x": -290,
        "origin_z": -290,
        "image": "player_data/minimaps/GrandRift_Minimap.png"
    },
    "Lockdown": {
        "scale": 1000,
        "origin_x": -500,
        "origin_z": -500,
        "image": "player_data/minimaps/Lockdown_Minimap.jpg"
    }
}

# -----------------------------
# LOAD DATA
# -----------------------------

@st.cache_data
def load_data():

    frames = []

    for folder in os.listdir(DATA_PATH):

        if "February" not in folder:
            continue

        folder_path = os.path.join(DATA_PATH, folder)

        for file in os.listdir(folder_path):

            filepath = os.path.join(folder_path, file)

            try:
                table = pq.read_table(filepath)
                df = table.to_pandas()
                df["date"] = folder
                frames.append(df)

            except:
                continue

    df = pd.concat(frames, ignore_index=True)

    df["event"] = df["event"].apply(
        lambda x: x.decode("utf-8") if isinstance(x, bytes) else x
    )

    
    return df

df = load_data()

st.success(f"Loaded {len(df)} rows")

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------

st.sidebar.header("Filters")

date = st.sidebar.selectbox(
    "Select Date",
    sorted(df["date"].unique())
)

date_df = df[df["date"] == date]

map_selected = st.sidebar.selectbox(
    "Select Map",
    sorted(date_df["map_id"].unique())
)

map_df = date_df[date_df["map_id"] == map_selected]

match_id = st.sidebar.selectbox(
    "Select Match",
    sorted(map_df["match_id"].unique())
)

match_df = map_df[map_df["match_id"] == match_id].copy()
match_df = match_df.sort_values("ts")

# -----------------------------
# VISUALIZATION TOGGLES
# -----------------------------

st.sidebar.header("Visualization Layers")

show_paths = st.sidebar.checkbox("Player Paths", True)
show_kills = st.sidebar.checkbox("Kills", True)
show_deaths = st.sidebar.checkbox("Deaths", True)
show_loot = st.sidebar.checkbox("Loot", True)
show_storm = st.sidebar.checkbox("Storm Deaths", True)

# -----------------------------
# TIMELINE
# -----------------------------

match_df["ts_seconds"] = match_df["ts"].astype("int64") // 10**9

start_time = match_df["ts_seconds"].min()

match_df["match_time"] = match_df["ts_seconds"] - start_time

min_ts = int(match_df["match_time"].min())
max_ts = int(match_df["match_time"].max())

if min_ts == max_ts:
    time_selected = max_ts
else:
    time_selected = st.slider(
        "Match Time (seconds)",
        min_ts,
        max_ts,
        max_ts
    )

timeline_df = match_df[
    match_df["match_time"] <= time_selected
]

# -----------------------------
# MAP COORDINATE CONVERSION
# -----------------------------

config = MAP_CONFIG[map_selected]

scale = config["scale"]
origin_x = config["origin_x"]
origin_z = config["origin_z"]

def world_to_map(x, z):

    u = (x - origin_x) / scale
    v = (z - origin_z) / scale

    px = u * 1024
    py = (1 - v) * 1024

    return px, py


coords = timeline_df.apply(
    lambda r: world_to_map(r["x"], r["z"]),
    axis=1
)

timeline_df["px"] = [c[0] for c in coords]
timeline_df["py"] = [c[1] for c in coords]

# -----------------------------
# EVENT GROUPS
# -----------------------------

movement = timeline_df[
    timeline_df["event"].isin(["Position", "BotPosition"])
]

kills = timeline_df[
    timeline_df["event"].isin(["Kill", "BotKill"])
]

deaths = timeline_df[
    timeline_df["event"].isin(["Killed", "BotKilled"])
]

storm = timeline_df[
    timeline_df["event"] == "KilledByStorm"
]

loot = timeline_df[
    timeline_df["event"] == "Loot"
]

# -----------------------------
# MATCH SUMMARY
# -----------------------------

st.subheader("Match Summary")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Players", match_df["user_id"].nunique())
col2.metric("Kills", len(kills))
col3.metric("Deaths", len(deaths))
col4.metric("Loot", len(loot))

# -----------------------------
# MAP VISUALIZATION
# -----------------------------

st.subheader("Player Movement")

fig = go.Figure()

img = Image.open(config["image"])

fig.add_layout_image(
    dict(
        source=img,
        x=0,
        y=0,
        sizex=1024,
        sizey=1024,
        xref="x",
        yref="y",
        layer="below"
    )
)

# PLAYER PATHS

if show_paths:

    for player, group in movement.groupby("user_id"):

        player_type = "Bot" if str(player).isdigit() else "Human"

        color = "orange" if player_type == "Bot" else "red"
        width = 1 if player_type == "Bot" else 3

        fig.add_trace(
            go.Scatter(
                x=group["px"],
                y=group["py"],
                mode="lines",
                line=dict(color=color, width=width),
                name=player_type
            )
        )

# EVENT MARKERS

if show_kills:

    fig.add_trace(go.Scatter(
        x=kills["px"],
        y=kills["py"],
        mode="markers",
        marker=dict(size=10, color="green"),
        name="Kills"
    ))

if show_deaths:

    fig.add_trace(go.Scatter(
        x=deaths["px"],
        y=deaths["py"],
        mode="markers",
        marker=dict(size=10, color="black"),
        name="Deaths"
    ))

if show_storm:

    fig.add_trace(go.Scatter(
        x=storm["px"],
        y=storm["py"],
        mode="markers",
        marker=dict(size=12, color="purple", symbol="triangle-up"),
        name="Storm Deaths"
    ))

if show_loot:

    fig.add_trace(go.Scatter(
        x=loot["px"],
        y=loot["py"],
        mode="markers",
        marker=dict(size=6, color="yellow"),
        name="Loot"
    ))

fig.update_layout(
    width=900,
    height=900,
    yaxis=dict(scaleanchor="x", autorange="reversed")
)

st.plotly_chart(fig, use_container_width=True, key="map_plot")

# -----------------------------
# HEATMAPS
# -----------------------------

st.subheader("Kill Heatmap")

if len(kills) > 0:

    kill_heatmap = px.density_heatmap(
        kills,
        x="px",
        y="py",
        nbinsx=40,
        nbinsy=40
    )

    st.plotly_chart(kill_heatmap, use_container_width=True, key="kill_heatmap")

else:
    st.write("No kill events in this match.")

st.subheader("Death Heatmap")

if len(deaths) > 0:

    death_heatmap = px.density_heatmap(
        deaths,
        x="px",
        y="py",
        nbinsx=40,
        nbinsy=40
    )

    st.plotly_chart(death_heatmap, use_container_width=True, key="death_heatmap")

else:
    st.write("No death events in this match.")
