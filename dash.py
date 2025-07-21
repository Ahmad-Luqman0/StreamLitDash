import os
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import gdown
import zipfile
import shutil

# ---------- DOWNLOAD LOGS FROM GOOGLE DRIVE ----------
DRIVE_URL = "https://drive.google.com/drive/folders/1bgyqkfQCcTpGfbktc75gJrN1j5tj7tJ9"
LOGS_ZIP = "logs.zip"
BASE_PATH = "Logs"


def download_logs_from_drive():
    """Download and extract Logs folder from Google Drive if not already present."""
    if os.path.exists(BASE_PATH):
        return  # Already downloaded

    st.info("⏳ Downloading Logs folder from Google Drive... (only first run)")

    # Convert folder URL to sharable gdown link (export as zip)
    gdown.download_folder(DRIVE_URL, quiet=False, use_cookies=False)

    # If Google Drive is provided as a zip manually, handle it:
    if LOGS_ZIP in os.listdir():
        with zipfile.ZipFile(LOGS_ZIP, "r") as zip_ref:
            zip_ref.extractall()
        os.remove(LOGS_ZIP)

    st.success("✅ Logs downloaded successfully!")


# Download if needed
download_logs_from_drive()


@st.cache_data
def load_all_data(base_path):
    """Reads all CSVs, adds Day/Night classification, and links images."""
    all_data = []

    for mode in ["entry", "exit"]:
        mode_path = os.path.join(base_path, mode)
        if not os.path.exists(mode_path):
            continue

        for folder in os.listdir(mode_path):
            folder_path = os.path.join(mode_path, folder)
            if not os.path.isdir(folder_path):
                continue

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

                    # ---------- ENTRY LOGIC ----------
                    if mode == "entry":
                        df["time_of_day"] = (
                            "Night" if i >= len(csv_files) - 3 else "Day"
                        )
                        csv_prefix = csv_file.split("_entry_log")[0]
                        images_folder = os.path.join(
                            folder_path, f"{csv_prefix}_images"
                        )

                    # ---------- EXIT LOGIC (FIXED) ----------
                    else:
                        if csv_file.startswith("night_exit_log"):
                            df["time_of_day"] = "Night"
                            images_folder = os.path.join(folder_path, "night_images")
                        else:
                            df["time_of_day"] = "Day"
                            csv_prefix = csv_file.split("_exit_log")[0]
                            images_folder = os.path.join(
                                folder_path, f"{csv_prefix}_images"
                            )

                    if "plate" not in df.columns:
                        df["plate"] = None

                    if images_folder and os.path.exists(images_folder):
                        df["image_path"] = df["image"].apply(
                            lambda x: os.path.join(images_folder, x)
                        )
                    else:
                        df["image_path"] = None

                    df["mode"] = mode.capitalize()
                    all_data.append(df)

                except Exception as e:
                    print(f"Skipping {csv_path}: {e}")

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()


# ---------- LOAD DATA ----------
df_all = load_all_data(BASE_PATH)

st.title("Vehicle Entry/Exit Dashboard")

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
mode_options = ["Entry", "Exit"]
selected_mode = st.sidebar.multiselect(
    "Select Mode:", options=mode_options, default=mode_options
)

filtered_df = df_all[
    (df_all["date"].isin(selected_dates))
    & (df_all["time_of_day"].isin(selected_time))
    & (df_all["mode"].isin(selected_mode))
]

# ---------- KPI METRICS ----------
st.metric("Total Vehicles", len(filtered_df))

# ---------- DAILY TREND (MATPLOTLIB) ----------
daily_counts = (
    filtered_df.groupby(["date", "time_of_day", "mode"])
    .size()
    .reset_index(name="vehicle_count")
)

if not daily_counts.empty:
    st.subheader("📊 Daily Vehicle Count (Day vs Night, Entry vs Exit)")

    for mode in ["Entry", "Exit"]:
        mode_data = daily_counts[daily_counts["mode"] == mode]
        if mode_data.empty:
            continue

        pivot_df = mode_data.pivot(
            index="date", columns="time_of_day", values="vehicle_count"
        ).fillna(0)

        fig, ax = plt.subplots(figsize=(8, 4))
        pivot_df.plot(kind="bar", ax=ax, color=["#1f77b4", "#ff7f0e"])
        ax.set_title(f"{mode} Vehicles")
        ax.set_ylabel("Vehicle Count")
        ax.set_xlabel("Date")
        ax.tick_params(axis="x", rotation=90)
        ax.legend(title="Time of Day")
        st.pyplot(fig)

# ---------- TABLE WITH MULTIPLE SELECTION ----------
st.subheader("📋 Vehicles Table (Select to View Images)")

if not filtered_df.empty:
    table_df = filtered_df[
        ["id", "plate", "mode", "date", "time_of_day", "image_path"]
    ].reset_index(drop=True)

    if "selected_rows" not in st.session_state:
        st.session_state.selected_rows = []

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

    st.session_state.selected_rows = list(
        edited_df[edited_df["View Image"] == True].index
    )

    if st.button("🧹 Clear All Selections"):
        st.session_state.selected_rows = []
        st.rerun()

    if st.session_state.selected_rows:
        st.subheader("🖼️ Selected Vehicle Images")
        for idx in st.session_state.selected_rows:
            row = table_df.loc[idx]
            if row["image_path"] and os.path.exists(row["image_path"]):
                st.image(
                    row["image_path"],
                    width=300,
                    caption=f"{row['mode']} | Vehicle ID: {row['id']} | Plate: {row['plate']}",
                )
            else:
                st.warning(
                    f"No image available for {row['mode']} | Vehicle ID: {row['id']} | Plate: {row['plate']}"
                )
    else:
        st.info("Select one or more vehicles to view their images.")
else:
    st.info("No data available for the selected filters.")
