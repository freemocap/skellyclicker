from pathlib import Path
import pandas as pd
import cv2
import logging

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


def fill_in_labelled_data_folder(path_to_videos_for_training: Path,
        path_to_dlc_project_folder: Path,
        path_to_image_labels_csv: Path,
        scorer_name: str = "scorer"
        ):

    labels_dataframe = pd.read_csv(path_to_image_labels_csv)
    per_video_dataframe = dict(
        tuple(labels_dataframe.groupby("video")))  # create dataframe per video (to simplify indexing below)

    header_df, joint_names = build_dlc_formatted_header(labels_dataframe=labels_dataframe, scorer_name=scorer_name)

    labeled_frames_per_video = {}
    for video_name, video_df in per_video_dataframe.items():
        video_name_wo_extension = str(video_name).split('.')[0]
        dlc_video_folder_path = path_to_dlc_project_folder / 'labeled-data' / video_name_wo_extension
        dlc_video_folder_path.mkdir(parents=True, exist_ok=True)

        # TODO: be able to look in different locations to handle multiple video folders
        # Or is it better to run this function for each video set (each with own CSV?)
        video_path = path_to_videos_for_training / f"{video_name}"
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        cap = cv2.VideoCapture(str(video_path))
        labeled_frames = []
        frame_idx = 0
        
        # Initialize a DataFrame with the MultiIndex structure
        df = header_df.copy()
        
        logger.info(f'Looking for labeled frames for {video_path}')
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret or frame_idx >= len(video_df):
                break

            row = video_df.iloc[frame_idx, 2:]  # Keep this line to check for non-NaN values

            if not row.isna().all():  # if a frame is labeled (any of the x/y values are filled in/not NaNs)
                labeled_frames.append(video_df.iloc[frame_idx]["frame"])

                image_name = f'img{frame_idx:03d}.png'
                image_save_path = dlc_video_folder_path / image_name
                if not image_save_path.exists():
                    cv2.imwrite(filename=str(image_save_path),
                                img=frame)

                # Create the path format for the index
                image_path = f"labeled-data\\{video_name_wo_extension}\\{image_name}"
                
                # Build a row for this frame
                frame_data = {}
                for joint in joint_names:
                    x_val = video_df[video_df['frame'] == frame_idx][f"{joint}_x"].values[0]
                    y_val = video_df[video_df['frame'] == frame_idx][f"{joint}_y"].values[0]
                    frame_data[(scorer_name, joint, 'x')] = x_val
                    frame_data[(scorer_name, joint, 'y')] = y_val
                
                # Add this frame to the DataFrame
                df.loc[image_path] = frame_data

            frame_idx += 1

        cap.release()
        
        # Save the CSV file 
        output_csv_path = dlc_video_folder_path / f'CollectedData_{scorer_name}.csv'
        df.to_csv(output_csv_path)
        
        # Save the H5 file
        output_h5_path = dlc_video_folder_path / f'CollectedData_{scorer_name}.h5'
        df.to_hdf(str(output_h5_path), key = "df_with_missing", format="table", mode="w")
        
        logger.info(f'Saved DLC formatted CSV to {output_csv_path}')
        logger.info(f'Saved DLC formatted H5 to {output_h5_path}')
        
        labeled_frames_per_video[video_name] = labeled_frames

    logger.info("\n=== Summary of Labeled Frames ===")
    for video, frames in labeled_frames_per_video.items():
        logger.info(f"{video}: {frames}")


if __name__ == '__main__':
    path_to_dlc_project_folder = Path(r"C:\Users\Aaron\Documents\your-project-name-Aaron-2025-04-01")
    path_to_image_labels_csv = Path(r"C:\Users\Aaron\Downloads\output.csv")

    fill_in_labelled_data_folder(path_to_recording=Path(r"C:\Users\Aaron\FreeMocap_Data\recording_sessions\freemocap_test_data"),
        path_to_dlc_project_folder=path_to_dlc_project_folder,
        path_to_image_labels_csv=path_to_image_labels_csv)