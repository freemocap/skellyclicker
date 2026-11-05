import pandas as pd
import numpy as np
from pathlib import Path

if __name__=='__main__':
    machine_labels_path = Path("/home/scholl-lab/ferret_recordings/session_2025-07-01_ferret_757_EyeCameras_P33_EO5/full_recording/mocap_data/dlc_output/toy_model_v2/skellyclicker_machine_labels_iteration_9.csv")
    timestamps_path = Path("/home/scholl-lab/ferret_recordings/session_2025-07-01_ferret_757_EyeCameras_P33_EO5/full_recording/mocap_data/synchronized_corrected_videos/24676894_synchronized_timestamps_utc.npy")
    output_path = Path("/home/scholl-lab/Dropbox/projects/VisBehavDev/data/session_2025-07-01_ferret_757_EyeCameras_P33_EO5/full_recording/toy_2d_tidy.csv")
    df = pd.read_csv(machine_labels_path)
    timestamps = np.load(timestamps_path)

    timestamp_list = []
    for idx, row in df.iterrows():
        # print(row["frame"])
        timestamp_list.append(timestamps[row["frame"]])

    df["timestamps"] = timestamp_list
    df.to_csv(output_path)