import os
import zipfile
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# ---------- SETTINGS ----------
ZIP_FILE = "logs.zip"
BASE_PATH = "Logs"  # ✅ Extracted folder name

# ---------- HELPER: Extract logs.zip ----------
@st.cache_data
def extract_logs():
    if os.path.exists(BASE_PATH) and os.listdir(BASE_PATH):
        return True

    if not os.path.exists(ZIP_FILE):
        st.error("❌ logs.zip not found!")
        return False

    try:
        with zipfile.ZipFile(ZIP_FILE, "r") as zip_ref:
            zip_ref.extractall(BASE_PATH)
        return True
    except zipfile.BadZipFile:
        st.error("❌ Bad zip file! Please upload a valid logs.zip.")
        return False

# ---------- DEBUG: Print folder structure ----------
def list_folders_recursive(root_folder):
    folder_structure = {}
    for root, dirs, files in os.walk(root_folder):
        folder_structure[root] = {"dirs": dirs, "files": files}
    return folder_structure

# ---------- DATA LOADER ----------
@st.cache_data
def load_all_data(base_path):
    all_data = []

    # ✅ Make folder names case-insensitive (Entry or entry, Exit or exit)
    available_folders = {f.lower(): f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))}

    for mode in ["entry", "exit"]:
        if mode not in available_folders:
            continue

        mode_path = os.path.join(base_path, available_folders[mode])

        for folder in os.listdir(mode_path):
            folder_path = os.path.join(mode_path, folder)
            if not os.path.isdir(folder_path):
                continue

            csv_files = sorted([f for f in os.listdir(folder_path) if f.endswith(".csv")])
            for i, csv_file in enumerate(csv_files):
                csv_path = os.path.join(folder_path, csv_file)
                try:
                    df = pd.read_csv(csv_path)
                    if df.empty:
                        continue

                    df["date"] = pd.to_datetime(folder, format="%d-%m-%Y").date()

                    # ---------- ENTRY LOGIC ----------
                    if mode == "entry":
                        df["time_of_day"] = "Night" if i >= len(csv_files) - 3 else "Day"
                        csv_prefix = csv_file.split("_entry_log")[0]
                        images_folder = os.path.join(folder_path, f"{csv_prefix}_images")

                    # ---------- EXIT LOGIC ----------
                    else:
                        if "night" in csv_file.lower():
                            df["time_of_day"] = "Night"
                            night_folder = os.path.join(folder_path, f"{folder} night_images")
                            images_folder = night_folder if os.path.exists(night_folder) else os.path.join(folder_path, "night_images")
                        else:
                            df["time_of_day"] = "Day"
                            day_folder = os.path.join(folder_path, f"{folder} day_images")
                            images_folder = day_folder if os.path.exists(day_folder) else os.path.join(folder_path, f"{csv_file.split('_exit_log')[0]}_images")

                    if "plate" not in df.columns:
                        df["plate"] = None

                    if images_folder and os.path.exists(images_folder):
                        df["image_path"] = df["image"].apply(lambda x: os.path.join(images_folder, x))
                    else:
                        df["image_path"] = None

                    df["mode"] = mode.capitalize()
                    all_data.append(df)

                except Exception as e:
                    print(f"Skipping {csv_path}: {e}")

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

# ---------- MAIN APP ----------
st.title("🚗 Vehicle Entry/Exit Dashboard")

if extract_logs():
    # ✅ Print folder structure for debugging
    st.subheader("📂 Extracted Folder Structure (Debug)")
    st.json(list_folders_recursive(BASE_PATH))

    df_all = load_all_data(BASE_PATH)
else:
    st.stop()

if df_all.empty:
    st.warning("No valid data found!")
    st.stop()

# ---------- FILTERS ----------
st.sidebar.header("Filters")
available_dates = sorted(df_all["date"].unique())
selected_dates = st.sidebar.multiselect("Select Dates:", options=available_dates, default=available_dates)
time_options = ["Day", "Night"]
selected_time = st.sidebar.multiselect("Select Time of Day:", options=time_options, default=time_options)
mode_options = ["Entry", "Exit"]
selected_mode = st.sidebar.multiselect("Select Mode:", options=mode_options, default=mode_options)

filtered_df = df_all[(df_all["date"].isin(selected_dates)) & (df_all["time_of_day"].isin(selected_time)) & (df_all["mode"].isin(selected_mode))]

# ---------- KPI METRICS ----------
st.metric("Total Vehicles", len(filtered_df))

# ---------- DAILY TREND ----------
daily_counts = filtered_df.groupby(["date", "time_of_day", "mode"]).size().reset_index(name="vehicle_count")
if not daily_counts.empty:
    st.subheader("📊 Daily Vehicle Count (Day vs Night, Entry vs Exit)")
    for mode in ["Entry", "Exit"]:
        mode_data = daily_counts[daily_counts["mode"] == mode]
        if mode_data.empty:
            continue

        pivot_df = mode_data.pivot(index="date", columns="time_of_day", values="vehicle_count").fillna(0)
        fig, ax = plt.subplots(figsize=(8, 4))
        pivot_df.plot(kind="bar", ax=ax, color=["#1f77b4", "#ff7f0e"])
        ax.set_title(f"{mode} Vehicles")
        ax.set_ylabel("Vehicle Count")
        ax.set_xlabel("Date")
        ax.tick_params(axis="x", rotation=90)
        ax.legend(title="Time of Day")
        st.pyplot(fig)

# ---------- FIRST & LAST VEHICLE EVENT ----------
st.subheader("⏳ First and Last Vehicle Event (Daily Basis)")
event_summary = []
for date in sorted(df_all["date"].unique()):
    day_df = df_all[df_all["date"] == date]
    for mode in ["Entry", "Exit"]:
        mode_df = day_df[day_df["mode"] == mode]
        if mode_df.empty:
            continue
        first_row, last_row = mode_df.iloc[0], mode_df.iloc[-1]
        event_summary.append({
            "Date": date,
            "Mode": mode,
            "First Vehicle ID": first_row["id"],
            "First Plate": first_row["plate"],
            "First Image Path": first_row["image_path"],
            "Last Vehicle ID": last_row["id"],
            "Last Plate": last_row["plate"],
            "Last Image Path": last_row["image_path"],
        })

event_summary_df = pd.DataFrame(event_summary)
if not event_summary_df.empty:
    if "selected_first_last_rows" not in st.session_state:
        st.session_state.selected_first_last_rows = []

    event_summary_df["View Images"] = event_summary_df.index.isin(st.session_state.selected_first_last_rows)

    edited_df = st.data_editor(
        event_summary_df.drop(columns=["First Image Path", "Last Image Path"]),
        column_config={
            "View Images": st.column_config.CheckboxColumn("👁 View Images", help="Check to view images for this row", default=False)
        },
        hide_index=True,
        use_container_width=True,
        key="first_last_table",
    )
    st.session_state.selected_first_last_rows = list(edited_df[edited_df["View Images"] == True].index)

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
                    st.image(row["First Image Path"], width=300, caption=f"First {row['Mode']} | ID: {row['First Vehicle ID']} | Plate: {row['First Plate']}")
                else:
                    st.warning(f"No image for First {row['Mode']}")
            with cols[1]:
                if row["Last Image Path"] and os.path.exists(row["Last Image Path"]):
                    st.image(row["Last Image Path"], width=300, caption=f"Last {row['Mode']} | ID: {row['Last Vehicle ID']} | Plate: {row['Last Plate']}")
                else:
                    st.warning(f"No image for Last {row['Mode']}")

# ---------- VEHICLES TABLE ----------
st.subheader("📋 Vehicles Table (Select to View Images)")
if not filtered_df.empty:
    table_df = filtered_df[["id", "plate", "mode", "date", "time_of_day", "image_path"]].reset_index(drop=True)
    if "selected_rows" not in st.session_state:
        st.session_state.selected_rows = []
    table_df["View Image"] = table_df.index.isin(st.session_state.selected_rows)

    edited_df = st.data_editor(
        table_df.drop(columns=["image_path"]),
        column_config={
            "View Image": st.column_config.CheckboxColumn("🔍 Select to View Image", help="You can select multiple vehicles", default=False)
        },
        hide_index=True,
        use_container_width=True,
        key="table_editor",
    )
    st.session_state.selected_rows = list(edited_df[edited_df["View Image"] == True].index)

    if st.button("🧹 Clear All Selections"):
        st.session_state.selected_rows = []
        st.rerun()

    if st.session_state.selected_rows:
        st.subheader("🖼️ Selected Vehicle Images")
        for idx in st.session_state.selected_rows:
            row = table_df.loc[idx]
            if row["image_path"] and os.path.exists(row["image_path"]):
                st.image(row["image_path"], width=300, caption=f"{row['mode']} | Vehicle ID: {row['id']} | Plate: {row['plate']}")
            else:
                st.warning(f"No image available for {row['mode']} | Vehicle ID: {row['id']} | Plate: {row['plate']}")
else:
    st.info("No data available for the selected filters.")
