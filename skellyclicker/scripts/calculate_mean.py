import numpy as np
import pandas as pd
from pathlib import Path


if __name__=='__main__':
    labels_path = Path("/home/scholl-lab/ferret_recordings/session_2025-07-11_ferret_757_EyeCamera_P43_E15__1/clips/0m_37s-1m_37s/mocap_data/dlc_output/skellyclicker_machine_labels_iteration_1.csv")
    df = pd.read_csv(labels_path)
    print(df.head(5))
    print(df.columns)

    # for eye videos:
    # selected_columns_x = [column for column in df.columns if "p" in column and "_x" in column]
    # selected_columns_y = [column for column in df.columns if "p" in column and "_y" in column]
    # print(selected_columns_y)

    # df['eye_mean_x'] = df[selected_columns_x].mean(axis=1)
    # df['eye_mean_y'] = df[selected_columns_y].mean(axis=1)

    # print(df.head(5))

    # df.to_csv(labels_path.parent.parent / "eye_data_with_mean.csv")

    #  for mocap videos:
    selected_columns_x = ['nose_x','left_cam_tip_x', 'right_cam_tip_x', 'base_x', 'left_eye_x', 'right_eye_x', 'left_ear_x', 'right_ear_x']
    selected_columns_y = ['nose_y','left_cam_tip_y', 'right_cam_tip_y', 'base_y', 'left_eye_y', 'right_eye_y', 'left_ear_y', 'right_ear_y']

    print(selected_columns_y)

    df['head_mean_x'] = df[selected_columns_x].mean(axis=1)
    df['head_mean_y'] = df[selected_columns_y].mean(axis=1)

    print(df.head(5))

    df.to_csv(labels_path.parent.parent / "head_data_with_mean.csv")


