from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import altair as alt

import streamlit as st

from data_loader import load_dashboard_data

ROOT = Path(__file__).resolve().parent.parent  # repo root
OUTPUTS = ROOT / "outputs"
UPLOAD_DIR = ROOT / "data" / "raw"

try:
    import traffic_intelligence  # noqa: F401
    PIPELINE_AVAILABLE = True
except ImportError:
    PIPELINE_AVAILABLE = False

_LEVEL_COLORS = {"LOW": "#28a745", "MODERATE": "#fd7e14", "HIGH": "#dc3545"}

st.set_page_config(page_title="Smart Traffic Monitoring", layout="wide")
st.title("AI-Based Smart Traffic Monitoring")
st.caption(
    "Vehicle detection, tracking, pedestrian counting, "
    "and traffic congestion analysis."
)


def convert_to_h264(src: Path) -> Path:
    """Re-encode to H.264 so browsers can play it."""
    import imageio_ffmpeg
    dst = src.with_name(f"{src.stem}_h264{src.suffix}")
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-i", str(src),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(dst),
        ],
        check=True,
        capture_output=True,
    )
    return dst


def run_pipeline(video_path: Path) -> tuple[bool, str]:
    cmd = [sys.executable, "-m", "traffic_intelligence", "run",
           "--input", str(video_path)]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log = (result.stdout or "") + "\n" + (result.stderr or "")
    return result.returncode == 0, log


def render(data) -> None:
    summary = data.summary
    traffic_level = summary.get("traffic_level", "N/A")
    level_color = _LEVEL_COLORS.get(traffic_level, "#6c757d")
    avg_speed = summary.get("average_vehicle_speed_kmh")

    st.subheader("Traffic Overview")
    cols = st.columns(4)
    cols[0].metric("Total Vehicles", summary.get("total_vehicles", 0))
    cols[1].metric("Pedestrians", summary.get("total_pedestrians", 0))
    with cols[2]:
        st.markdown("**Traffic Level**")
        st.markdown(
            f"<span style='font-size:2rem;font-weight:700;"
            f"color:{level_color}'>{traffic_level}</span>",
            unsafe_allow_html=True,
        )
    cols[3].metric(
        "Average Vehicle Speed",
        f"{avg_speed:.1f} km/h" if avg_speed is not None else "N/A",
    )

    st.subheader("Annotated Traffic Video")
    if data.annotated_video_path is not None:
        st.video(str(data.annotated_video_path))
    else:
        st.warning("Annotated video not found.")

    vehicles = data.tracks[data.tracks["class_name"] != "person"]

    st.subheader("Vehicles by Class")
    if not vehicles.empty:
        class_counts = vehicles["class_name"].value_counts().reset_index()
        class_counts.columns = ["class_name", "count"]
        chart = (
            alt.Chart(class_counts)
            .mark_bar()
            .encode(
                x=alt.X("class_name", title="Vehicle Type"),
                y=alt.Y("count", title="Number of Vehicles"),
                tooltip=["class_name", "count"],
            )
        )
        st.altair_chart(chart, width="stretch")
    else:
        st.info("No vehicles detected.")

    st.subheader("Vehicle Speed Analysis")
    if summary.get("speed_estimated") and not vehicles.empty:
        st.caption(
            "Speed values are approximate estimates based on typical vehicle "
            "dimensions. They are not calibrated measurements."
        )
        speed_data = vehicles.dropna(subset=["avg_speed_kmh"])
        if not speed_data.empty:
            speed_data = speed_data.assign(
                vehicle=lambda df: "#" + df["track_id"].astype(str)
                + " " + df["class_name"]
            )
            chart = (
                alt.Chart(speed_data)
                .mark_bar()
                .encode(
                    x=alt.X("vehicle", title="Tracked Vehicle"),
                    y=alt.Y("avg_speed_kmh",
                            title="Estimated Average Speed (km/h)"),
                    tooltip=["vehicle", "avg_speed_kmh", "max_speed_kmh"],
                )
            )
            st.altair_chart(chart, width="stretch")
        else:
            st.info("No vehicle speed data available.")
    else:
        st.info("Speed estimation is unavailable.")

    with st.expander("View Raw Track Data"):
        st.dataframe(data.tracks, width="stretch")


# ---------------- Sidebar: choose source ----------------
modes = (["Upload new video"] if PIPELINE_AVAILABLE else []) + ["View saved results"]
mode = st.sidebar.radio("Mode", modes)

if mode == "Upload new video":
    uploaded = st.file_uploader("Upload a traffic video",
                                type=["mp4", "mov", "avi", "mkv"])

    if uploaded is not None:
        st.video(uploaded)  # preview of the original upload

        if st.button("Run analysis", type="primary"):
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            video_path = UPLOAD_DIR / uploaded.name
            video_path.write_bytes(uploaded.getbuffer())

            with st.spinner("Processing video... this can take a few minutes."):
                ok, log = run_pipeline(video_path)

            if not ok:
                st.error("Pipeline failed.")
                st.code(log[-3000:])
                st.stop()

            data = load_dashboard_data(OUTPUTS)
            vp = data.annotated_video_path
            if vp is not None and "_h264" not in vp.stem:
                with st.spinner("Preparing video for the browser..."):
                    convert_to_h264(vp)
                data = load_dashboard_data(OUTPUTS)

            st.session_state["result"] = data

    if "result" in st.session_state:
        st.success("Analysis complete.")
        data = st.session_state["result"]
        if data.tracks.empty:
            st.warning("No tracks were produced for this video.")
        else:
            render(data)

else:
    options = {"Traffic Video 1": "video1", "Traffic Video 2": "video2"}
    choice = st.sidebar.selectbox("Select Traffic Video", list(options))
    data = load_dashboard_data(OUTPUTS / options[choice])
    if data.tracks.empty:
        st.warning(f"No pipeline outputs found for {choice}.")
    else:
        render(data)