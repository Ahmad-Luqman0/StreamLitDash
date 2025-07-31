import streamlit as st
import os
import csv
from PIL import Image
import pandas as pd

# Streamlit Page Setup
st.set_page_config(page_title="Vehicle Entry Log Dashboard", layout="wide")
st.title("Vehicle Entry Log Dashboard")

# Log folder path (hardcoded)
log_folder = os.path.join("Logs", "DCIM-A")

# Check if folder exists
if not os.path.exists(log_folder):
    st.error(f"Log folder not found at: {log_folder}")
    st.stop()

# Find all logs
log_files = sorted([f for f in os.listdir(log_folder) if f.endswith("_log.csv")])

# Total counters
total_cars = 0
video_stats = []

# Read log files
for log_file in log_files:
    video_name = log_file.replace("_log.csv", "")
    log_path = os.path.join(log_folder, log_file)
    try:
        with open(log_path, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
            count = len(rows)
            total_cars += count
            video_stats.append((video_name, count, rows))
    except Exception as e:
        st.warning(f"Could not read {log_file}: {e}")

# Display total
st.subheader(f"Total Cars Across All Videos: {total_cars}")

# Select video
video_names = [v[0] for v in video_stats]
selected_video = st.selectbox("Select a video log to view", video_names)

# Display images and table from selected video
for video_name, count, rows in video_stats:
    if video_name == selected_video:
        st.markdown(f"### 🎥 Video: {video_name} — Total Cars: {count}")

        # Display interactive table
        df = pd.DataFrame(rows)
        if not df.empty:
            selected_index = st.dataframe(
                df[["TrackID", "Timestamp"]],
                use_container_width=True,
                selection_mode="single",
            )

            # Get selected row
            selected_row = st.session_state.get("dataframe_selection")
            if selected_row is not None:
                try:
                    selected_path = df.iloc[selected_row["row"]]["ImagePath"]
                    if os.path.exists(selected_path):
                        st.image(
                            Image.open(selected_path),
                            caption=selected_path,
                            use_column_width=True,
                        )
                    else:
                        st.warning(f"Image not found: {selected_path}")
                except Exception as e:
                    st.warning(f"Error loading image: {e}")
        break
