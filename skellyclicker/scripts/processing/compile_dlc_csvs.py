import pandas as pd
import numpy as np
from pathlib import Path


def compile_dlc_csvs(
    path_to_folder_with_dlc_csvs: Path,
    confidence_threshold: float = 0.5,
):
    csv_list = sorted(
        list(path_to_folder_with_dlc_csvs.glob("*.csv"))
    )

    for csv in csv_list:
        if "filtered" in csv.name:
            csv_list.remove(csv)

    data = {}

    for csv in csv_list:
        camera_name = csv.stem.split("_")[0]

        df = pd.read_csv(csv, header=[1, 2])
        df = df.iloc[:, 1:]  # first column just has the headers

        # Check if data shape is as expected
        if df.shape[1] % 3 != 0:
            print(f"Unexpected number of columns in {csv}: {df.shape[1]}")
            continue

        data_array_with_confidence = np.array(
            df.values.reshape(df.shape[0], df.shape[1] // 3, 3)
        )  # (num_frames, num_markers, 3)
        thresholded_array = apply_confidence_threshold(
            array=data_array_with_confidence, threshold=confidence_threshold
        )

        data[camera_name] = thresholded_array[
            :, :, :2
        ]

    return data


def apply_confidence_threshold(array: np.ndarray, threshold: float) -> np.ndarray:
    """
    Set X,Y values to NaN where the corresponding confidence value is below threshold.
    """
    mask = array[..., 2] < threshold  # Shape: (num_cams, num_frames, num_markers)
    array[mask, 0] = np.nan  # Set X to NaN where confidence is low
    array[mask, 1] = np.nan  # Set Y to NaN where confidence is low
    return array


if __name__ == "__main__":
    path_to_folder_with_dlc_csvs = Path(
        "/Users/philipqueen/session_2025-07-11_ferret_757_EyeCamera_P43_E15__1/clips/0m_37s-1m_37s/mocap_data/dlc_output/head_body_eyecam_v1_model_outputs_iteration_17/"
    )
    dlc_data_dict = compile_dlc_csvs(
        path_to_folder_with_dlc_csvs, confidence_threshold=0.5
    )

    print(dlc_data_dict.keys())
    print([value.shape for value in dlc_data_dict.values()])
