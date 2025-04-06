import logging
from pathlib import Path

import cv2
import numpy as np
from pydantic import BaseModel

from skellyclicker.core.video_handler import VideoHandler

logger = logging.getLogger(__name__)
MAX_WINDOW_SIZE = (1920, 1080)
ZOOM_STEP = 1.1
ZOOM_MIN = 1.0
ZOOM_MAX = 10.0
POSITION_EPSILON = 1e-6  # Small threshold for position changes

TRACKED_POINTS_JSON_PATH = Path(__file__).parent.parent / "tracked_points.json"
DEMO_VIDEO_PATH = (
        Path.home()
        / "freemocap_data/recording_sessions/freemocap_test_data/synchronized_videos"
)
if not TRACKED_POINTS_JSON_PATH.exists():
    logger.error(f"Tracked points JSON file not found: {TRACKED_POINTS_JSON_PATH}")
    exit(1)



class SkellyClicker(BaseModel):
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


    @classmethod
    def create(
            cls,
            video_folder: str,
            max_window_size: tuple[int, int] = MAX_WINDOW_SIZE,
            data_handler_path: str = str(TRACKED_POINTS_JSON_PATH),
            machine_labels_path: str | None = None
    ):
        return cls(
            video_handler=VideoHandler.from_folder(
                video_folder = video_folder,
                max_window_size = max_window_size,
                data_handler_path = data_handler_path,
                machine_labels_path = machine_labels_path
            ),
            video_folder=video_folder,
            max_window_size=max_window_size,
        )

    @property
    def frame_count(self):
        return self.video_handler.frame_count

    def _handle_keypress(self, key: int):
        if key == 27:  # ESC
            return False
        elif key == 32:  # spacebar
            self.is_playing = not self.is_playing
        elif key == ord("r"):  # reset zoom
            for video in self.video_handler.videos:
                video.zoom_state.reset()
        elif key == ord("a"):
            self._jump_n_frames(-1)
        elif key == ord("d"):
            self._jump_n_frames(1)
        elif key == ord("w"):
            self.video_handler.move_active_point_by_index(index_change=-1)
        elif key == ord("s"):
            self.video_handler.move_active_point_by_index(index_change=1)
        elif key == ord("q"):
            self.keyboard_zoom(zoom_in=False) # Zoom out
        elif key == ord("e"):
            self.keyboard_zoom(zoom_in=True)
        elif key == ord("h"):
            self.show_help = not self.show_help
            self.video_handler.image_annotator.config.show_help = self.show_help
        elif key == ord("u"):
            self.clear_current_point()
        elif key == ord("c"):
            self.auto_next_point = not self.auto_next_point
        elif key == ord("m"):
            self.video_handler.show_machine_labels = not self.video_handler.show_machine_labels
        elif key == ord("n"):
            self.video_handler.image_annotator.config.show_names = not self.video_handler.image_annotator.config.show_names
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

    def clear_current_point(self):
        video_index = None
        if self.active_cell is not None:
            video_index = self.active_cell[1] * self.video_handler.grid_parameters.columns + self.active_cell[0]
        if not video_index:
            return
        self.video_handler.data_handler.clear_current_point(video_index=video_index, frame_number=self.frame_number)

    def _jump_n_frames(self, num_frames: int = 1):
        self.is_playing = False
        self.frame_number += num_frames
        self.frame_number = max(0, self.frame_number)
        self.frame_number = min(self.frame_count, self.frame_number)

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
        if video_idx < len(self.video_handler.videos):
            video = self.video_handler.videos[video_idx]
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
            while True:
                key = cv2.waitKey(1) & 0xFF
                if not self._handle_keypress(key):
                    break
                grid_image = self.video_handler.create_grid_image(
                    self.frame_number, annotate_images=True
                )
                cv2.imshow(str(self.video_folder), grid_image)
                if self.is_playing:
                    self.frame_number = (self.frame_number + self.step_size) % self.frame_count
        finally:
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            self.video_handler.close()


if __name__ == "__main__":
    video_path = DEMO_VIDEO_PATH

    if not Path(video_path).exists():
        logger.error(f"Video path not found: {video_path}")
        exit(1)
    
    # To label a new session:
    data_path = TRACKED_POINTS_JSON_PATH

    # To continue labeling an existing session:
    # data_path = "/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/skellyclicker_data/2025-04-03_11-54-23_skellyclicker_output.csv"

    # display machine labels (DLC predictions)
    machine_labels_path = None
    # machine_labels_path = "/Users/philipqueen/DLCtest/sample_data_test2_user_20250403/model_outputs_iteration_0/skellyclicker_machine_labels_iteration_0.csv"


    viewer = SkellyClicker.create(video_folder=str(video_path), data_handler_path=str(data_path), machine_labels_path=machine_labels_path)
    viewer.run()