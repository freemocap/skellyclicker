import cv2
import numpy as np
import pandas as pd
from pathlib import Path

from skellyclicker.core.click_data_handler.data_handler import DataHandler
from skellyclicker.core.video_handler.image_annotator import ImageAnnotator, ImageAnnotatorConfig

if __name__=='__main__':
    labels_path = Path("/home/scholl-lab/deeplabcut_data/toy_only_2/model_outputs/model_outputs_iteration_2/skellyclicker_machine_labels_iteration_2.csv")
    video_folder = Path('/home/scholl-lab/recordings/session_2025-07-11/ferret_757_EyeCameras_P43_E15__1/basler_pupil_synchronized')
    # video_paths = [video_folder / "eye0.mp4", video_folder / "rotated_eye_1.mp4"]
    # video_paths = [video_folder / "eye0_clipped_4451_11621.mp4", video_folder / "eye1_clipped_4469_11638.mp4"]
    video_paths = [video_folder / "25006505.mp4", video_folder / "25000609.mp4", video_folder / "24908832.mp4", video_folder / "24908831.mp4", video_folder / "24676894.mp4"]
    # video_paths = list(video_folder.glob("*.mp4"))
    print(video_paths)
    for path in video_paths:
        if not path.exists():
            raise ValueError(f"no file found at {path}")
    print(f"found videos: {video_paths}")

    # output_path = video_folder.parent / "annotated_videos"
    output_path = Path("/home/scholl-lab/recordings/session_2025-07-11/ferret_757_EyeCameras_P43_E15__1/dlc_annotated_videos/toy")
    output_path.mkdir(exist_ok=True)


    data_handler = DataHandler.from_csv(labels_path) 

    annotator_config = ImageAnnotatorConfig(
        marker_thickness=3,
        show_names=False, 
        tracked_points=sorted(data_handler.tracked_points), 
        show_clicks=False, 
        show_help=False
    )
    image_annotator = ImageAnnotator(config=annotator_config)

    for video in video_paths:
        video_name = video.stem
        cap = cv2.VideoCapture(str(video))

        framerate = cap.get(cv2.CAP_PROP_FPS)
        framesize = (
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )
        fourcc = cv2.VideoWriter.fourcc(*"mp4v")  # need to deal with higher frame rates
        print(f"writing video to {str(output_path / video.name)}")

        video_writer_object = cv2.VideoWriter(
            str(output_path / video.name), fourcc, round(framerate, 2), framesize
        )

        frame_number = -1
        while True:
            ret, frame = cap.read()
            frame_number += 1
            if not ret:
                print(f"failed to read frame {frame_number}")
                break

            click_data = data_handler.get_data_by_video_name_and_frame(video_name=video_name, frame_number=frame_number)

            annotated_frame = image_annotator.annotate_single_image(image=frame,  click_data=click_data)
            video_writer_object.write(annotated_frame)
        video_writer_object.release()
        cap.release()



    # df = pd.read_csv(labels_path)

    # print(df.head(5))
    # print(df.columns)