import logging
import sys
import threading
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict

from skellyclicker import MAX_WINDOW_SIZE, POSITION_EPSILON
from skellyclicker.core.video_handler.video_handler import VideoHandler

logger = logging.getLogger(__name__)

TRACKED_POINTS_JSON_PATH = (
    Path(__file__).parent.parent.parent.parent / "tracked_points.json"
)
DEMO_VIDEO_PATH = (
    Path.home()
    / "freemocap_data/recording_sessions/freemocap_test_data/synchronized_videos"
)
if not TRACKED_POINTS_JSON_PATH.exists():
    logger.error(f"Tracked points JSON file not found: {TRACKED_POINTS_JSON_PATH}")
    exit(1)


class VideoViewer(BaseModel):
    video_folder: str
    max_window_size: tuple[int, int]
    video_handler: VideoHandler
    frame_number: int = 0
    is_playing: bool = True
    step_size: int = 1
    zoom_scale: float = 1.0
    zoom_center: tuple[int, int] = (0, 0)
    active_cell: tuple[int, int] | None = None  # Track which cell the mouse is in
    last_mouse_position: tuple[int, int] | None = None
    show_help: bool = False
    auto_next_point: bool = True
    show_names: bool = True
    video_thread: threading.Thread | None = None
    model_config = ConfigDict(arbitrary_types_allowed=True)
    should_continue: bool = True
    on_complete: Callable | None = None

    def launch_video_thread(self):
        if sys.platform == "darwin":  # OpenCV GUI can only open in main thread on Mac
            self.video_thread = None
            self.run()
        elif sys.platform == "linux":
            self.video_thread = None
            self.run()
        else:
            self.video_thread = threading.Thread(target=self.run)
            self.video_thread.daemon = True
            self.video_thread.start()

    @classmethod
    def from_videos(
        cls,
        video_paths: list[str],
        max_window_size: tuple[int, int] = MAX_WINDOW_SIZE,
        data_handler_path: str = str(TRACKED_POINTS_JSON_PATH),
        machine_labels_path: str | None = None,
    ):
        return cls(
            video_handler=VideoHandler.from_videos(
                video_paths=video_paths,
                max_window_size=max_window_size,
                data_handler_path=data_handler_path,
                machine_labels_path=machine_labels_path,
            ),
            video_folder=str(Path(video_paths[0]).parent),
            max_window_size=max_window_size,
        )

    @property
    def frame_count(self):
        return self.video_handler.frame_count

    def _handle_keypress(self, key: int) -> bool:
        if key == 27:  # ESC
            return False
        elif key == 32:  # spacebar
            self.is_playing = not self.is_playing
        elif key == ord("r"):  # reset zoom
            for video in self.video_handler.videos.values():
                video.zoom_state.reset()
        elif key == ord("a"):
            self._jump_n_frames(-1)
        elif key == ord("d"):
            self._jump_n_frames(1)
        elif key == ord("f"):
            self._jump_to_labeled_frame(reverse=True)
        elif key == ord("g"):
            self._jump_to_labeled_frame(reverse=False)
        elif key == ord("w"):
            self.video_handler.move_active_point_by_index(index_change=-1)
        elif key == ord("s"):
            self.video_handler.move_active_point_by_index(index_change=1)
        elif key == ord("q"):
            self.keyboard_zoom(zoom_in=False)  # Zoom out
        elif key == ord("e"):
            self.keyboard_zoom(zoom_in=True)
        elif key == ord("h"):
            # TODO: fix help depending on video height
            self.show_help = not self.show_help
            self.video_handler.image_annotator.config.show_help = self.show_help
        elif key == ord("u"):
            self.clear_current_point()
        elif key == ord("c"):
            self.auto_next_point = not self.auto_next_point
        elif key == ord("v"):
            self.video_handler.copy_frame_data_from_machine_labels(
                self.frame_number,
                video_index=self.active_cell[1]
                * self.video_handler.grid_parameters.columns
                + self.active_cell[0],
            )
        elif key == ord("m"):
            self.video_handler.show_machine_labels = (
                not self.video_handler.show_machine_labels
            )
            print(
                f"Machine labels visibility: {self.video_handler.show_machine_labels}"
            )
        elif key == ord("n"):
            self.video_handler.image_annotator.config.show_names = (
                not self.video_handler.image_annotator.config.show_names
            )
            if self.video_handler.machine_labels_annotator is not None:
                self.video_handler.machine_labels_annotator.config.show_names = (
                    self.video_handler.image_annotator.config.show_names
                )
        elif key == ord(","):
            self.video_handler.image_annotator.config.show_clicks = (
                not self.video_handler.image_annotator.config.show_clicks
            )
        elif key == ord("1"):
            self._change_brightness(increase=False)
        elif key == ord("2"):
            self._change_brightness(increase=True)
        elif key == ord("3"):
            self._change_contrast(increase=False)
        elif key == ord("4"):
            self._change_contrast(increase=True)
        elif key == ord("5"):
            self._reset_brightness_contrast()
        elif key == ord('i'):
            self.keyboard_pan((0, -1))  # Pan up
        elif key == ord('k'):
            self.keyboard_pan((0, 1))  # Pan down
        elif key == ord('j'):
            self.keyboard_pan((-1, 0))  # Pan left
        elif key == ord('l'):
            self.keyboard_pan((1, 0))  # Pan right
        return True

    def keyboard_zoom(self, zoom_in: bool = True):
        flags = 1 if zoom_in else -1
        if self.active_cell is not None and self.last_mouse_position is not None:
            self._zoom(
                self.last_mouse_position[0],
                self.last_mouse_position[1],
                flags=flags,
                cell_x=self.active_cell[0],
                cell_y=self.active_cell[1],
            )

    def keyboard_pan(self, direction: tuple[int, int]):
        if self.active_cell is None:
            return
        cell_x, cell_y = self.active_cell
        video_idx = cell_y * self.video_handler.grid_parameters.columns + cell_x
        if video_idx >= len(self.video_handler.videos.values()):
            return
        video = list(self.video_handler.videos.values())[video_idx]

        pan_amount = 10
        video.zoom_state.center_x += direction[0] * pan_amount
        video.zoom_state.center_y += direction[1] * pan_amount

    def _change_contrast(self, increase: bool = True):
        if self.active_cell is None:
            return
        cell_x, cell_y = self.active_cell
        video_idx = cell_y * self.video_handler.grid_parameters.columns + cell_x
        if video_idx >= len(self.video_handler.videos.values()):
            return
        video = list(self.video_handler.videos.values())[video_idx]

        if video.contrast == 1:
            change = 1 if increase else -0.1
            video.contrast = max(0, video.contrast + change)
        elif video.contrast > 1 and video.contrast < 1.5:
            change = 1 if increase else 1 - video.contrast
        elif video.contrast < 1:
            change = 0.1 if increase else -0.1
            video.contrast = max(0, video.contrast + change)
        else:
            change = 1 if increase else -1
            video.contrast = min(video.contrast + change, 10)


    def _change_brightness(self, increase: bool = True):
        if self.active_cell is None:
            return
        cell_x, cell_y = self.active_cell
        video_idx = cell_y * self.video_handler.grid_parameters.columns + cell_x
        if video_idx >= len(self.video_handler.videos.values()):
            return
        video = list(self.video_handler.videos.values())[video_idx]

        change = 10 if increase else -10
        video.brightness = min(max(-120, video.brightness + change), 120)

    def _reset_brightness_contrast(self):
        if self.active_cell is None:
            return
        cell_x, cell_y = self.active_cell
        video_idx = cell_y * self.video_handler.grid_parameters.columns + cell_x
        if video_idx >= len(self.video_handler.videos.values()):
            return
        video = list(self.video_handler.videos.values())[video_idx]

        video.brightness = 0
        video.contrast = 1


    def clear_current_point(self):
        video_index = None
        if self.active_cell is not None:
            video_index = (
                self.active_cell[1] * self.video_handler.grid_parameters.columns
                + self.active_cell[0]
            )
        if video_index is None:
            return
        self.video_handler.data_handler.clear_current_point(
            video_index=video_index, frame_number=self.frame_number
        )

    def _jump_n_frames(self, num_frames: int = 1):
        self.is_playing = False
        self.frame_number += num_frames
        self.frame_number = max(0, self.frame_number)
        self.frame_number = min(self.frame_count, self.frame_number)

    def _jump_to_labeled_frame(self, reverse: bool = False):
        self.is_playing = False
        labeled_frames = self.video_handler.data_handler.get_nonempty_frames()
        if not labeled_frames or len(labeled_frames) == 0:
            logger.warning(
                "Jump to next labeled frame pressed, but no labeled frames found in the current video."
            )
            return
        compare_function = (
            (lambda x: x < self.frame_number)
            if reverse
            else (lambda x: x > self.frame_number)
        )
        eligible_frames = [
            frame_number
            for frame_number in labeled_frames
            if compare_function(frame_number)
        ]
        next_frame = (
            max(eligible_frames, default=labeled_frames[-1])
            if reverse
            else min(eligible_frames, default=labeled_frames[0])
        )
        self.frame_number = next_frame

    def _mouse_callback(self, event, x, y, flags, param):
        # Calculate which grid cell contains the mouse
        cell_x = x // self.video_handler.grid_parameters.cell_width
        cell_y = y // self.video_handler.grid_parameters.cell_height

        # Store current cell
        self.active_cell = (cell_x, cell_y)
        self.last_mouse_position = (x, y)

        if event == cv2.EVENT_LBUTTONDOWN:
            self.video_handler.handle_clicks(
                x, y, self.frame_number, auto_next_point=self.auto_next_point
            )
        elif event == cv2.EVENT_MOUSEWHEEL:
            # Only zoom if mouse is within a valid video cell
            self._zoom(x, y, flags, cell_x, cell_y)

    def _zoom(self, x, y, flags, cell_x, cell_y):
        video_idx = cell_y * self.video_handler.grid_parameters.columns + cell_x
        if video_idx < len(self.video_handler.videos.values()):
            video = list(self.video_handler.videos.values())[video_idx]
            scaling = video.scaling_params
            zoom_state = video.zoom_state

            # Get relative position within cell
            cell_relative_x = x % self.video_handler.grid_parameters.cell_width
            cell_relative_y = y % self.video_handler.grid_parameters.cell_height

            if zoom_state.scale > 1.0:
                # Calculate current visible region
                relative_x = (
                    zoom_state.center_x - scaling.x_offset
                ) / scaling.scaled_width
                relative_y = (
                    zoom_state.center_y - scaling.y_offset
                ) / scaling.scaled_height

                # Calculate center point in zoomed coordinates
                zoomed_width = int(scaling.scaled_width * zoom_state.scale)
                zoomed_height = int(scaling.scaled_height * zoom_state.scale)

                center_x = int(relative_x * zoomed_width)
                center_y = int(relative_y * zoomed_height)

                # Calculate visible region bounds
                x1 = max(0, center_x - scaling.scaled_width // 2)
                y1 = max(0, center_y - scaling.scaled_height // 2)

                # Convert mouse position to be relative to current visible region
                new_center_x = x1 + (cell_relative_x - scaling.x_offset)
                new_center_y = y1 + (cell_relative_y - scaling.y_offset)

                if abs(new_center_x - video.zoom_state.center_x) > POSITION_EPSILON:
                    video.zoom_state.center_x = scaling.x_offset + int(
                        new_center_x / zoom_state.scale
                    )
                if abs(new_center_y - video.zoom_state.center_y) > POSITION_EPSILON:
                    video.zoom_state.center_y = scaling.y_offset + int(
                        new_center_y / zoom_state.scale
                    )
            else:
                # Initial zoom, use raw cell coordinates
                video.zoom_state.center_x = cell_relative_x
                video.zoom_state.center_y = cell_relative_y

                # Update zoom scale
            if flags > 0:  # Scroll up to zoom in
                video.zoom_state.scale *= 1.1
            else:  # Scroll down to zoom out
                video.zoom_state.scale /= 1.1
            # Keep zoom scale within reasonable limits
            video.zoom_state.scale = np.clip(video.zoom_state.scale, 1.0, 10.0)

    def run(self):
        """Run the video grid viewer."""
        cv2.namedWindow(self.video_folder, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self.video_folder, *self.max_window_size)
        cv2.setMouseCallback(
            self.video_folder,
            lambda event, x, y, flags, param: self._mouse_callback(
                event, x, y, flags, param
            ),
        )

        try:
            while self.should_continue:
                key = cv2.waitKey(1) & 0xFF
                if not self._handle_keypress(key):
                    break
                grid_image = self.video_handler.create_grid_image(
                    self.frame_number, annotate_images=True
                )
                cv2.imshow(str(self.video_folder), grid_image)
                if self.is_playing:
                    self.frame_number = (
                        self.frame_number + self.step_size
                    ) % self.frame_count
        finally:
            print("closing videos")
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            if self.on_complete:
                self.on_complete()
            else:
                self.video_handler.close(save_data=None)

    def stop(self):
        self.should_continue = False


if __name__ == "__main__":
    video_path = DEMO_VIDEO_PATH

    if not Path(video_path).exists():
        logger.error(f"Video path not found: {video_path}")
        exit(1)

    video_paths = sorted([str(path) for path in Path(video_path).glob("*.mp4")])

    # To label a new session:
    data_path = TRACKED_POINTS_JSON_PATH

    # To continue labeling an existing session:
    # data_path = "/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/skellyclicker_data/2025-04-03_11-54-23_skellyclicker_output.csv"

    # display machine labels (DLC predictions)
    machine_labels_path = None
    # machine_labels_path = "/Users/philipqueen/DLCtest/sample_data_test2_user_20250403/model_outputs_iteration_0/skellyclicker_machine_labels_iteration_0.csv"

    viewer = VideoViewer.from_videos(
        video_paths=video_paths,
        data_handler_path=str(data_path),
        machine_labels_path=machine_labels_path,
    )
    viewer.run()
