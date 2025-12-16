import cv2
import shutil
from pathlib import Path
from enum import Enum

class FlipMethod(Enum):
    HORIZONTAL = 1
    VERTICAL = 0
    BOTH = -1


def flip_video(video: Path, flip_method: FlipMethod) -> Path:
    cap = cv2.VideoCapture(str(video))

    output_path = video.parent / f"{video.stem}_flipped.mp4"

    writer = cv2.VideoWriter(
        str(output_path),
        fourcc=cv2.VideoWriter.fourcc(*"mp4v"),
        fps=round(cap.get(cv2.CAP_PROP_FPS),2),
        frameSize=(int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    )

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Finished reading video")
            break

        flipped_frame = cv2.flip(frame, flip_method.value)

        writer.write(flipped_frame)

    cap.release()
    writer.release()

    return output_path

def flip_eye1_video(eye_data_folder: Path) -> Path:
    eye_videos_path = eye_data_folder / "eye_videos"
    eye0_video_path = list(eye_videos_path.glob("eye0*.mp4"))[0]
    eye1_video_path = list(eye_videos_path.glob("eye1*.mp4"))[0]
    flipped_videos_path = eye_videos_path / "flipped_eye_videos"
    flipped_videos_path.mkdir(parents=True, exist_ok=True)
    flipped_eye1 = flip_video(video=eye1_video_path, flip_method=FlipMethod.HORIZONTAL)

    shutil.copy2(eye0_video_path, flipped_videos_path)
    shutil.move(flipped_eye1, flipped_videos_path)

    return flipped_videos_path

def flip_eye0_video(eye_data_folder: Path) -> Path:
    eye_videos_path = eye_data_folder / "eye_videos"
    eye0_video_path = list(eye_videos_path.glob("eye0*.mp4"))[0]
    eye1_video_path = list(eye_videos_path.glob("eye1*.mp4"))[0]
    flipped_videos_path = eye_videos_path / "flipped_eye_videos"
    flipped_videos_path.mkdir(parents=True, exist_ok=True)
    flipped_eye0 = flip_video(video=eye0_video_path, flip_method=FlipMethod.VERTICAL)

    shutil.copy2(eye1_video_path, flipped_videos_path)
    shutil.move(flipped_eye0, flipped_videos_path)

    return flipped_videos_path

if __name__=='__main__':
    eye_data = Path("/home/scholl-lab/ferret_recordings/session_2025-10-20_ferret_420_E010/clips/2m_00s-3m_00s/eye_data")

    flip_eye0_video(eye_data_folder=eye_data)