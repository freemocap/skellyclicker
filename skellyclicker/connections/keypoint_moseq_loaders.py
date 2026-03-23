from pathlib import Path

import numpy as np
import pandas as pd


def load_skellyclicker_csv(
    filepath: str | Path,
    confidence_for_labeled: float = 1.0,
    confidence_for_unlabeled: float = 0.0,
) -> tuple[dict, dict, list[str]]:
    """Load a skellyclicker CSV into Keypoint MoSeq format.

    Args:
        filepath: Path to a skellyclicker-format CSV file.
        confidence_for_labeled: Confidence value assigned to labeled points (default 1.0).
        confidence_for_unlabeled: Confidence value for missing/unlabeled points (default 0.0).

    Returns:
        coordinates: dict mapping recording name → ndarray(num_frames, num_keypoints, 2)
        confidences: dict mapping recording name → ndarray(num_frames, num_keypoints)
        bodyparts: list of keypoint names in column order
    """
    df = pd.read_csv(filepath)
    df["video"] = df["video"].astype(str)
    df = df.set_index(["video", "frame"])

    # Extract ordered, deduplicated bodypart names from column headers
    bodyparts = []
    seen = set()
    for col in df.columns:
        name = col.removesuffix("_x").removesuffix("_y")
        if name not in seen:
            seen.add(name)
            bodyparts.append(name)

    coordinates = {}
    confidences = {}

    for video_name in df.index.get_level_values("video").unique():
        video_df = df.loc[video_name]
        frame_index = video_df.index
        num_frames = frame_index.max() + 1
        num_keypoints = len(bodyparts)

        coords = np.full((num_frames, num_keypoints, 2), np.nan)
        confs = np.full((num_frames, num_keypoints), confidence_for_unlabeled)

        for frame, row in video_df.iterrows():
            for kp_idx, point_name in enumerate(bodyparts):
                x = row.get(f"{point_name}_x", np.nan)
                y = row.get(f"{point_name}_y", np.nan)
                coords[frame, kp_idx, 0] = x
                coords[frame, kp_idx, 1] = y
                if not (np.isnan(x) or np.isnan(y)):
                    confs[frame, kp_idx] = confidence_for_labeled

        recording_key = Path(video_name).stem
        coordinates[recording_key] = coords
        confidences[recording_key] = confs

    return coordinates, confidences, bodyparts
