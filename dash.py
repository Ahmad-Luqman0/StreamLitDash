import os
import pandas as pd
import streamlit as st
import plotly.express as px

# ---------- SETTINGS ----------
BASE_PATH = "Logs"  # ✅ CHANGE THIS


@st.cache_data
def load_all_data(base_path):
    """Reads all CSVs, adds Day/Night classification, and links images."""
    all_data = []

    for folder in os.listdir(base_path):
        folder_path = os.path.join(base_path, folder)
        if os.path.isdir(folder_path):
            csv_files = sorted(
                [f for f in os.listdir(folder_path) if f.endswith(".csv")]
            )

            for i, csv_file in enumerate(csv_files):
                csv_path = os.path.join(folder_path, csv_file)
                try:
                    df = pd.read_csv(csv_path)
                    if df.empty:
                        continue

                    df["date"] = pd.to_datetime(folder, format="%d-%m-%Y").date()
                    df["time_of_day"] = "Night" if i >= len(csv_files) - 3 else "Day"
                    if "plate" not in df.columns:
                        df["plate"] = None

                    csv_prefix = csv_file.split("_entry_log")[0]
                    images_folder = os.path.join(folder_path, f"{csv_prefix}_images")

                    if os.path.exists(images_folder):
                        df["image_path"] = df["image"].apply(
                            lambda x: os.path.join(images_folder, x)
                        )
                    else:
                        df["image_path"] = None

                    all_data.append(df)
                except Exception as e:
                    print(f"Skipping {csv_path}: {e}")

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()


# ---------- LOAD DATA ----------
df_all = load_all_data(BASE_PATH)

st.title("🚗 Vehicle Entry/Exit Dashboard")

if df_all.empty:
    st.warning("No valid data found!")
    st.stop()

# ---------- FILTERS ----------
st.sidebar.header("Filters")

available_dates = sorted(df_all["date"].unique())
selected_dates = st.sidebar.multiselect(
    "Select Dates:", options=available_dates, default=available_dates
)
time_options = ["Day", "Night"]
selected_time = st.sidebar.multiselect(
    "Select Time of Day:", options=time_options, default=time_options
)

filtered_df = df_all[
    (df_all["date"].isin(selected_dates)) & (df_all["time_of_day"].isin(selected_time))
]

# ---------- KPI METRICS ----------
st.metric("Total Vehicles", len(filtered_df))

# ---------- DAILY TREND ----------
daily_counts = (
    filtered_df.groupby(["date", "time_of_day"])
    .size()
    .reset_index(name="vehicle_count")
)

if not daily_counts.empty:
    fig = px.bar(
        daily_counts,
        x="date",
        y="vehicle_count",
        color="time_of_day",
        barmode="group",
        title="Daily Vehicle Count (Day vs Night)",
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- TABLE WITH MULTIPLE SELECTION ----------
st.subheader("📋 Vehicles Table (Select to View Images)")

if not filtered_df.empty:
    table_df = filtered_df[
        ["id", "plate", "date", "time_of_day", "image_path"]
    ].reset_index(drop=True)

    # ✅ Maintain selected checkboxes in session state
    if "selected_rows" not in st.session_state:
        st.session_state.selected_rows = []

    # Add "View Image" column based on session state
    table_df["View Image"] = table_df.index.isin(st.session_state.selected_rows)

    edited_df = st.data_editor(
        table_df.drop(columns=["image_path"]),
        column_config={
            "View Image": st.column_config.CheckboxColumn(
                "🔍 Select to View Image",
                help="You can select multiple vehicles",
                default=False,
            )
        },
        hide_index=True,
        use_container_width=True,
        key="table_editor",
    )

    # ✅ Update session state with selected rows
    st.session_state.selected_rows = list(
        edited_df[edited_df["View Image"] == True].index
    )

    # ✅ "Clear All Selections" Button
    if st.button("🧹 Clear All Selections"):
        st.session_state.selected_rows = []
        st.rerun()

    # ✅ Display selected images
    if st.session_state.selected_rows:
        st.subheader("🖼️ Selected Vehicle Images")
        for idx in st.session_state.selected_rows:
            row = table_df.loc[idx]
            if row["image_path"] and os.path.exists(row["image_path"]):
                st.image(
                    row["image_path"],
                    width=300,
                    caption=f"Vehicle ID: {row['id']} | Plate: {row['plate']}",
                )
            else:
                st.warning(
                    f"No image available for Vehicle ID: {row['id']} | Plate: {row['plate']}"
                )
    else:
        st.info("Select one or more vehicles to view their images.")
else:
    st.info("No data available for the selected filters.")
