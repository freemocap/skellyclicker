import logging
import shutil
from pathlib import Path

import cv2
import pandas as pd

from skellyclicker.core.deeplabcut_handler.create_deeplabcut.create_deeplabcut_config import HUMAN_EXPERIMENTER_NAME

logger = logging.getLogger(__name__)


def build_dlc_formatted_header(labels_dataframe: pd.DataFrame, scorer_name: str):
    """Creates a dataframe with MultiIndex columns in DLC format"""
    # Extract joint names from the column names
    joint_names_dimension = labels_dataframe.columns.drop(['frame', 'video'])
    joint_names = sorted(set(col.rsplit('_', 1)[0] for col in joint_names_dimension))

    # Create MultiIndex columns
    column_tuples = []
    for joint in joint_names:
        column_tuples.append((scorer_name, joint, 'x'))
        column_tuples.append((scorer_name, joint, 'y'))

    multi_columns = pd.MultiIndex.from_tuples(column_tuples, names=['scorer', 'bodyparts', 'coords'])

    # Create empty DataFrame with MultiIndex columns
    header_df = pd.DataFrame(columns=multi_columns)

    return header_df, joint_names

def get_session_name(path_to_videos_for_training: str) -> str:
    path_parts = Path(path_to_videos_for_training).parts
    for part in path_parts:
        if part.startswith('session'):
            return part
        
    for part in path_parts:
        if part.startswith('Session'):
            return part
        
    raise ValueError(f"Session name not found in path: {path_to_videos_for_training} - must include string 'session'")


def fill_in_labelled_data_folder(path_to_videos_for_training: str,
                                 path_to_dlc_project_folder: str,
                                 path_to_image_labels_csv: str,
                                 scorer_name: str = HUMAN_EXPERIMENTER_NAME
                                 ):
    labels_dataframe = pd.read_csv(path_to_image_labels_csv)
    per_video_dataframe = dict(
        tuple(labels_dataframe.groupby("video")))  # create dataframe per video (to simplify indexing below)

    header_df, joint_names = build_dlc_formatted_header(labels_dataframe=labels_dataframe, scorer_name=scorer_name)

    labeled_frames_per_video = {}
    for video_name, video_df in per_video_dataframe.items():
        video_name_wo_extension = str(video_name).split('.')[0]
        session_name = get_session_name(path_to_videos_for_training)
        combined_name = f"{session_name}_{video_name_wo_extension}"
        dlc_video_folder_path = Path(path_to_dlc_project_folder) / 'labeled-data' / combined_name
        if dlc_video_folder_path.exists():
            shutil.rmtree(dlc_video_folder_path)
        dlc_video_folder_path.mkdir(parents=True)

        video_path = Path(path_to_videos_for_training) / f"{video_name}"
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        labeled_frames = []

        # Initialize a DataFrame with the MultiIndex structure
        df = header_df.copy()

        logger.info(f'Looking for labeled frames for {video_path}')

        labeled_rows = video_df[~video_df.iloc[:, 2:].isna().all(axis=1)]
        for _, row in labeled_rows.iterrows():
            frame_number = int(row["frame"])

            # Seek to the exact frame — must match skellyclicker's cap.set()/cap.read() behavior
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            if not ret:
                logger.warning(f"Could not read frame {frame_number} from {video_path}, skipping")
                continue

            labeled_frames.append(frame_number)

            image_name = f'img{frame_number:05d}.png'
            image_save_path = dlc_video_folder_path / image_name
            # Always overwrite: stale images from prior iterations must not persist
            cv2.imwrite(filename=str(image_save_path), img=frame)

            image_path = f"labeled-data/{combined_name}/{image_name}"

            frame_data = {}
            for joint in joint_names:
                frame_data[(scorer_name, joint, 'x')] = row[f"{joint}_x"]
                frame_data[(scorer_name, joint, 'y')] = row[f"{joint}_y"]

            df.loc[image_path] = frame_data

        cap.release()

        # Save the CSV file 
        output_csv_path = dlc_video_folder_path / f'CollectedData_{scorer_name}.csv'
        df.to_csv(output_csv_path)

        # Save the H5 file
        output_h5_path = dlc_video_folder_path / f'CollectedData_{scorer_name}.h5'
        df.to_hdf(str(output_h5_path), key="df_with_missing", format="table", mode="w")

        logger.info(f'Saved DLC formatted CSV to {output_csv_path}')
        logger.info(f'Saved DLC formatted H5 to {output_h5_path}')

        labeled_frames_per_video[video_name] = labeled_frames

    logger.info("\n=== Summary of Labeled Frames ===")
    for video, frames in labeled_frames_per_video.items():
        logger.info(f"{video}: {frames}")


if __name__ == '__main__':
    path_to_videos_for_training = ""
    path_to_dlc_project_folder = ""
    path_to_image_labels_csv = ""

    fill_in_labelled_data_folder(
        path_to_videos_for_training=path_to_videos_for_training,
        path_to_dlc_project_folder=path_to_dlc_project_folder,
        path_to_image_labels_csv=path_to_image_labels_csv)
