from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

import pandas as pd


@dataclass
class DashboardData:
    tracks: pd.DataFrame
    summary: dict
    annotated_video_path: Path | None


def load_dashboard_data(output_dir: Path) -> DashboardData:
    tracks_path = output_dir / "tracks" / "tracks.csv"
    summary_path = output_dir / "analytics" / "summary.json"

    tracks = (
        pd.read_csv(tracks_path)
        if tracks_path.exists()
        else pd.DataFrame()
    )

    summary = (
        json.loads(summary_path.read_text(encoding="utf-8"))
        if summary_path.exists()
        else {}
    )

    annotated_video_path = None

    if summary.get("annotated_video_path"):
        # Take only the file name, so Windows paths also work on the server
        file_name = PureWindowsPath(summary["annotated_video_path"]).name
        candidate = output_dir / "videos" / file_name

        h264_candidate = candidate.with_name(
            f"{candidate.stem}_h264{candidate.suffix}"
        )

        if h264_candidate.exists():
            annotated_video_path = h264_candidate
        elif candidate.exists():
            annotated_video_path = candidate

    return DashboardData(
        tracks=tracks,
        summary=summary,
        annotated_video_path=annotated_video_path,
    )