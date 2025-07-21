import os
import requests
import zipfile
import re
import streamlit as st

BASE_PATH = "Logs"
ZIP_FILE = "logs.zip"

ONEDRIVE_URL = "https://1drv.ms/u/c/df58e066d83ecacc/EU4eZHwPkytOk-PdIkXCaQEBGn2Nk9f0tXSpkl7DoSKyLg?e=oLJ1NB"


@st.cache_data(show_spinner="📥 Downloading and extracting logs...")
def download_and_extract_logs():
    # ✅ Convert OneDrive share link to direct download link
    def convert_onedrive_to_direct(onedrive_url: str) -> str:
        match = re.search(r"1drv\.ms/\w+/([^?]+)", onedrive_url)
        if not match:
            return onedrive_url  # fallback
        return f"https://api.onedrive.com/v1.0/shares/u!{onedrive_url.split('/')[-1].split('?')[0]}/root/content"

    direct_url = convert_onedrive_to_direct(ONEDRIVE_URL)

    if not os.path.exists(ZIP_FILE):
        st.info("📥 Downloading logs.zip from OneDrive...")
        response = requests.get(direct_url, allow_redirects=True)
        if response.status_code != 200:
            st.error("❌ Failed to download logs.zip. Check the link.")
            return
        with open(ZIP_FILE, "wb") as f:
            f.write(response.content)

    st.info("📂 Extracting logs.zip...")
    with zipfile.ZipFile(ZIP_FILE, "r") as zip_ref:
        zip_ref.extractall(".")
    st.success("✅ Logs downloaded & extracted successfully!")


# ---------- LOAD DATA ----------
@st.cache_data
def load_all_data(base_path):
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

                    # ENTRY LOGIC
                    if mode == "entry":
                        df["time_of_day"] = (
                            "Night" if i >= len(csv_files) - 3 else "Day"
                        )
                        csv_prefix = csv_file.split("_entry_log")[0]
                        images_folder = os.path.join(
                            folder_path, f"{csv_prefix}_images"
                        )

                    # EXIT LOGIC
                    else:
                        if "night" in csv_file.lower():
                            df["time_of_day"] = "Night"
                            night_folder = os.path.join(
                                folder_path, f"{folder} night_images"
                            )
                            images_folder = (
                                night_folder
                                if os.path.exists(night_folder)
                                else os.path.join(folder_path, "night_images")
                            )
                        else:
                            df["time_of_day"] = "Day"
                            day_folder = os.path.join(
                                folder_path, f"{folder} day_images"
                            )
                            images_folder = (
                                day_folder
                                if os.path.exists(day_folder)
                                else os.path.join(
                                    folder_path,
                                    f"{csv_file.split('_exit_log')[0]}_images",
                                )
                            )

                    if "plate" not in df.columns:
                        df["plate"] = None

                    df["image_path"] = (
                        df["image"].apply(lambda x: os.path.join(images_folder, x))
                        if images_folder and os.path.exists(images_folder)
                        else None
                    )

                    df["mode"] = mode.capitalize()
                    all_data.append(df)
                except Exception as e:
                    print(f"Skipping {csv_path}: {e}")

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()


df_all = load_all_data(BASE_PATH)

# ---------- STREAMLIT UI ----------
st.title("🚗 Vehicle Entry/Exit Dashboard")

if df_all.empty:
    st.warning("No valid data found!")
    st.stop()

# ---------- Filters ----------
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

# ---------- KPI ----------
st.metric("Total Vehicles", len(filtered_df))

# ---------- DAILY TREND ----------
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

# ---------- FIRST & LAST VEHICLE EVENT (DAILY BASIS) ----------
st.subheader("⏳ First and Last Vehicle Event (Daily Basis)")

event_summary = []

for date in sorted(df_all["date"].unique()):
    day_df = df_all[df_all["date"] == date]

    entry_df = day_df[day_df["mode"] == "Entry"]
    if not entry_df.empty:
        first_entry, last_entry = entry_df.iloc[0], entry_df.iloc[-1]
        event_summary.append(
            {
                "Date": date,
                "Mode": "Entry",
                "First Vehicle ID": first_entry["id"],
                "First Plate": first_entry["plate"],
                "First Image Path": first_entry["image_path"],
                "Last Vehicle ID": last_entry["id"],
                "Last Plate": last_entry["plate"],
                "Last Image Path": last_entry["image_path"],
            }
        )

    exit_df = day_df[day_df["mode"] == "Exit"]
    if not exit_df.empty:
        first_exit, last_exit = exit_df.iloc[0], exit_df.iloc[-1]
        event_summary.append(
            {
                "Date": date,
                "Mode": "Exit",
                "First Vehicle ID": first_exit["id"],
                "First Plate": first_exit["plate"],
                "First Image Path": first_exit["image_path"],
                "Last Vehicle ID": last_exit["id"],
                "Last Plate": last_exit["plate"],
                "Last Image Path": last_exit["image_path"],
            }
        )

event_summary_df = pd.DataFrame(event_summary)

if not event_summary_df.empty:
    if "selected_first_last_rows" not in st.session_state:
        st.session_state.selected_first_last_rows = []

    event_summary_df["View Images"] = event_summary_df.index.isin(
        st.session_state.selected_first_last_rows
    )

    edited_df = st.data_editor(
        event_summary_df.drop(columns=["First Image Path", "Last Image Path"]),
        column_config={
            "View Images": st.column_config.CheckboxColumn(
                "👁 View Images",
                help="Check to view images for this row",
                default=False,
            )
        },
        hide_index=True,
        use_container_width=True,
        key="first_last_table",
    )

    st.session_state.selected_first_last_rows = list(
        edited_df[edited_df["View Images"] == True].index
    )

    if st.button("🧹 Clear All Selections (First & Last Events)"):
        st.session_state.selected_first_last_rows = []
        st.rerun()

    if st.session_state.selected_first_last_rows:
        st.subheader("🖼️ Selected Vehicle Images")
        for idx in st.session_state.selected_first_last_rows:
            row = event_summary_df.loc[idx]
            st.markdown(f"### {row['Date']} - {row['Mode']}")
            cols = st.columns(2)

            with cols[0]:
                if row["First Image Path"] and os.path.exists(row["First Image Path"]):
                    st.image(
                        row["First Image Path"],
                        width=300,
                        caption=f"First {row['Mode']} | ID: {row['First Vehicle ID']} | Plate: {row['First Plate']}",
                    )
                else:
                    st.warning(f"No image for First {row['Mode']}")

            with cols[1]:
                if row["Last Image Path"] and os.path.exists(row["Last Image Path"]):
                    st.image(
                        row["Last Image Path"],
                        width=300,
                        caption=f"Last {row['Mode']} | ID: {row['Last Vehicle ID']} | Plate: {row['Last Plate']}",
                    )
                else:
                    st.warning(f"No image for Last {row['Mode']}")
    else:
        st.info("✅ Select rows from the table above to view images.")
else:
    st.info("No first or last vehicle events found.")

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
        st.subheader("Selected Vehicle Images")
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
