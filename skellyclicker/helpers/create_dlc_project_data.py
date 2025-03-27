from pathlib import Path
import pandas as pd
import cv2

from skellyclicker.__main__ import DEMO_VIDEO_PATH

import logging
logger = logging.getLogger(__name__)

def build_dlc_formatted_header(labels_dataframe: pd.DataFrame, scorer_name: str):
    "Creates a dataframe in the DLC format for labeled videos"
    joint_names_dimension = labels_dataframe.columns.drop(['frame', 'video'])
    joint_names = set(col.rsplit('_', 1)[0] for col in joint_names_dimension)
    columns = [("scorer", "bodyparts", "coords"), ("", "", ""), ("", "", "")]
    for joint in joint_names:
        for coord in ['x', 'y']:
            columns.append((scorer_name, joint, coord))

    columns = pd.MultiIndex.from_tuples(columns)
    return pd.DataFrame(columns=columns), joint_names


def run(path_to_recording: Path,
        path_to_dlc_project_folder: Path,
        path_to_image_labels_csv: Path,
        scorer_name: str = "Scorer"
        ):
    path_to_videos_for_training = path_to_recording / 'synchronized_videos'  # Will need to adjust for ferret lab path
    recording_name = path_to_recording.stem

    labels_dataframe = pd.read_csv(path_to_image_labels_csv)
    per_video_dataframe = dict(
        tuple(labels_dataframe.groupby("video")))  # create dataframe per video (to simplify indexing below)

    dlc_dataframe, joint_names = build_dlc_formatted_header(labels_dataframe=labels_dataframe, scorer_name=scorer_name)

    labeled_frames_per_video = {}
    for video_name, video_df in per_video_dataframe.items():
        video_name_wo_extension = str(video_name).split('.')[0]
        dlc_video_folder_path = path_to_dlc_project_folder / 'labeled-data' / video_name_wo_extension
        dlc_video_folder_path.mkdir(parents=True, exist_ok=True)

        video_path = path_to_videos_for_training / str(video_name)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        labeled_frames = []
        frame_idx = 0
        this_vid_dlc_df = dlc_dataframe.copy()
        logger.info(f'Looking for labeled frames for {video_path}')
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame_idx >= len(video_df):
                break

            row = video_df.iloc[frame_idx, 2:]

            if not row.isna().all():  # if a frame is labeled (any of the x/y values are filled in/not NaNs)
                labeled_frames.append(video_df.iloc[frame_idx]["frame"])

                image_name = f'img{frame_idx:03d}.png'
                cv2.imwrite(filename=str(dlc_video_folder_path / image_name),
                            img=frame)

                # fill in dataframe for this labeled frame
                dlc_row = ["labeled-data", video_name_wo_extension, image_name]
                for joint in joint_names:
                    x_val = video_df[video_df['frame'] == frame_idx][f"{joint}_x"].values[0]
                    y_val = video_df[video_df['frame'] == frame_idx][f"{joint}_y"].values[0]
                    dlc_row.extend([x_val, y_val])

                this_vid_dlc_df.loc[len(this_vid_dlc_df)] = dlc_row

            frame_idx += 1

        cap.release()
        this_vid_dlc_df.to_csv(dlc_video_folder_path / f'CollectedData_{scorer_name}.csv',
                               index=False)

        logger.info(f'Saved DLC formmated CSV to {dlc_video_folder_path}')
        labeled_frames_per_video[video_name] = labeled_frames

    logger.info("\n=== Summary of Labeled Frames ===")
    for video, frames in labeled_frames_per_video.items():
        logger.info(f"{video}: {frames}")


if __name__ == '__main__':

    path_to_dlc_project_folder = Path(r"D:\deeplabcut-projects\freemocap_test_data-jon-2025-03-27")
    path_to_image_labels_csv = Path(r"C:\Users\jonma\freemocap_data\recording_sessions\freemocap_test_data\skellyclicker\2025-03-27_10-32-49skellyclicker_output.csv")

    run(path_to_recording=DEMO_VIDEO_PATH.parent,
        path_to_dlc_project_folder=path_to_dlc_project_folder,
        path_to_image_labels_csv=path_to_image_labels_csv)