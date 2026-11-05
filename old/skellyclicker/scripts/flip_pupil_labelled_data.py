import pandas as pd
from pathlib import Path

from skellyclicker.scripts.flip_video import FlipMethod, flip_video

PUPIL_VIDEO_HEIGHT = 400
PUPIL_VIDEO_WIDTH = 400

def swap_columns(df: pd.DataFrame, column_1: str, column_2: str) -> pd.DataFrame:
    df[column_1], df[column_2] = df[column_2].copy(), df[column_1].copy()
    return df

def flip_pupil_data_horizontal(df: pd.DataFrame) -> pd.DataFrame:
    # swap p2 and p8 columns
    df = swap_columns(df, "p2_x", "p8_x")
    df = swap_columns(df, "p2_y", "p8_y")

    # swap p3 and p7 columns
    df = swap_columns(df, "p3_x", "p7_x")
    df = swap_columns(df, "p3_y", "p7_y")

    # flip p4 and p6 columns
    df = swap_columns(df, "p4_x", "p6_x")
    df = swap_columns(df, "p4_y", "p6_y")

    return df

def flip_pupil_data_vertical(df: pd.DataFrame) -> pd.DataFrame:
    # swap p8 and p6 columns
    df = swap_columns(df, "p6_x", "p8_x")
    df = swap_columns(df, "p6_y", "p8_y")

    # swap p1 and p5 columns
    df = swap_columns(df, "p1_x", "p5_x")
    df = swap_columns(df, "p1_y", "p5_y")

    # swap p2 and p4 columns
    df = swap_columns(df, "p2_x", "p4_x")
    df = swap_columns(df, "p2_y", "p4_y")

    return df

def flip_pupil_data_in_image_vertical(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    y_cols = [col for col in df.columns if '_y' in col]
    for col in y_cols:
        print(f"Vertical flipping data in {col}")
        df[col] = PUPIL_VIDEO_HEIGHT - df[col]
    return df

def flip_pupil_data_in_image_horizontal(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    x_cols = [col for col in df.columns if '_x' in col]
    for col in x_cols:
        print(f"Horizontal flipping data in {col}")
        df[col] = PUPIL_VIDEO_WIDTH - df[col]
    return df


if __name__=='__main__':
    df_path = Path("/home/scholl-lab/ferret_recordings/session_2025-10-11_ferret_420_E02/base_data/skellyclicker_data/2025-12-07_12-02-14_skellyclicker_output.csv")
    video_path = Path("/home/scholl-lab/ferret_recordings/session_2025-10-11_ferret_420_E02/base_data/pupil_output/eye0.mp4")

    df = pd.read_csv(df_path)

    df = flip_pupil_data_horizontal(df)
    df = flip_pupil_data_vertical(df)
    df = flip_pupil_data_in_image_horizontal(df)
    df = flip_pupil_data_in_image_vertical(df)

    new_df_name = f"{df_path.stem}_corrected_pupil_orientation"
    df.to_csv(df_path.with_stem(new_df_name), index=False)
    print(f"Saved csv to {new_df_name}")

    print("Flipping video")
    flip_video(video=video_path, flip_method=FlipMethod.BOTH)

