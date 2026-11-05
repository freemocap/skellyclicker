import cv2
from pathlib import Path

def synchronize_eye_videos(eye_video_path: Path, output_folder: Path):
    eye_videos = list(eye_video_path.glob("*.mp4"))

    if len(eye_videos) != 2:
        print(f"eye video path: {eye_video_path}")
        print(f"paths: {eye_videos}")
        raise ValueError(f"Expected two videos, but found {len(eye_videos)} instead")
    
    video_0 = cv2.VideoCapture(str(eye_videos[0]))
    video_1 = cv2.VideoCapture(str(eye_videos[1]))

    writer_0 = cv2.VideoWriter(
        str(output_folder / f"{eye_videos[0].stem}_synchronized.mp4"),
        fourcc=cv2.VideoWriter.fourcc(*"mp4v"),
        fps=round(video_0.get(cv2.CAP_PROP_FPS), 2),
        frameSize=(int(video_0.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video_0.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    )

    writer_1 = cv2.VideoWriter(
        str(output_folder / f"{eye_videos[1].stem}_synchronized.mp4"),
        fourcc=cv2.VideoWriter.fourcc(*"mp4v"),
        fps=round(video_1.get(cv2.CAP_PROP_FPS), 2),
        frameSize=(int(video_1.get(cv2.CAP_PROP_FRAME_WIDTH)), int(video_1.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    )

    while True:
        ret, video_0_frame = video_0.read()
        if not ret:
            break
        ret, video_1_frame = video_1.read()
        if not ret:
            break

        writer_0.write(video_0_frame)
        writer_1.write(video_1_frame)

    video_0.release()
    video_1.release()
    writer_0.release()
    writer_1.release()

    print("Done synchronizing videos")

if __name__=='__main__':
    eye_video_path = Path("/home/scholl-lab/ferret_recordings/session_2025-07-01_ferret_757_EyeCameras_P33_EO5/clips/1m_20s-2m_20s/eye_data/eye_videos")
    output_folder = eye_video_path.parent / "synchronized_eye_videos"

    output_folder.mkdir(exist_ok=True, parents=True)

    synchronize_eye_videos(eye_video_path=eye_video_path, output_folder=output_folder)