from pathlib import Path

import numpy as np
import pandas as pd


def load_skellyclicker_csv(
    filepath: str | Path,
) -> tuple[dict, dict, list[str]]:
    """Load a skellyclicker CSV into Keypoint MoSeq format.

    If the CSV contains {point}_confidence columns (e.g. from DLC machine labels),
    those values are used as confidences. Otherwise all labeled points get confidence 1.0.

    Args:
        filepath: Path to a skellyclicker-format CSV file.
        confidence_for_unlabeled: Confidence value for missing/unlabeled points (default 0.0).

    Returns:
        coordinates: dict mapping recording name → ndarray(num_frames, num_keypoints, 2)
        confidences: dict mapping recording name → ndarray(num_frames, num_keypoints)
        bodyparts: list of keypoint names in column order
    """
    df = pd.read_csv(filepath)
    df["video"] = df["video"].astype(str)
    df = df.set_index(["video", "frame"])

    # Extract ordered, deduplicated bodypart names from _x/_y columns only
    bodyparts = []
    seen = set()
    for col in df.columns:
        if col.endswith("_x") or col.endswith("_y"):
            name = col[:-2]
            if name not in seen:
                seen.add(name)
                bodyparts.append(name)

    coordinates = {}
    confidences = {}

    for video_name in df.index.get_level_values("video").unique():
        video_df = df.loc[video_name]
        num_frames = video_df.index.max() + 1
        num_keypoints = len(bodyparts)

        coords = np.full((num_frames, num_keypoints, 2), np.nan)
        confs = np.zeros((num_frames, num_keypoints))
        for frame, row in video_df.iterrows():
            for kp_idx, point_name in enumerate(bodyparts):
                x = row.get(f"{point_name}_x", np.nan)
                y = row.get(f"{point_name}_y", np.nan)
                coords[frame, kp_idx, 0] = x
                coords[frame, kp_idx, 1] = y
                if not (np.isnan(x) or np.isnan(y)):
                    confs[frame, kp_idx] = row.get(f"{point_name}_confidence", 1.0)

        recording_key = Path(video_name).stem
        coordinates[recording_key] = coords
        confidences[recording_key] = confs

    return coordinates, confidences, bodyparts
