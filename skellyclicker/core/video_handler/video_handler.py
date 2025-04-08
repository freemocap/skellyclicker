import logging
from pathlib import Path

import cv2
import numpy as np
from pydantic import BaseModel

from skellyclicker import VideoNameString
from skellyclicker.core.image_annotator import ImageAnnotator
from skellyclicker.core.video_handler.video_models import VideoPlaybackObject, VideoGridHelper, VideoGridScalingParameters

logger = logging.getLogger(__name__)


class VideoHandler(BaseModel):
    videos: dict[VideoNameString, VideoPlaybackObject] = []
    video_grid_helper: VideoGridHelper
    image_annotator: ImageAnnotator = ImageAnnotator()

    # show_machine_labels: bool = False
    # machine_labels_handler: DataHandler | None
    # machine_labels_annotator: ImageAnnotator | None

    @classmethod
    def from_videos(cls,
                    video_paths: list[str],
                    ):
        videos = {}
        for video_path in video_paths:
            if not Path(video_path).exists():
                raise ValueError(f"Video path does not exist: {video_path}")
            videos[video_path] = VideoPlaybackObject.from_file(
                path=video_path,
            )
        cls._validate_frame_counts(videos)

        video_grid_parameters = VideoGridHelper.calculate(videos=videos)
        for grid_index, video in enumerate(videos.values()):
            video.grid_scale = cls._calculate_scaling_parameters(
                original_width=video.metadata.width,
                original_height=video.metadata.height,
                grid_index=grid_index,
                video_grid_parameters=video_grid_parameters
            )

        return cls(videos=videos,
                   video_grid_helper=video_grid_parameters,
                   )

    def get_grid_image(self, frame_number: int) -> np.ndarray:
        """Create a grid of video images."""
        grid_image = self.video_grid_helper.create_blank_grid_image()

        for video_name, video in self.videos.items():
            image = video.get_frame(frame_number=frame_number)
            scaled_image = cv2.resize(image,
                                      (video.grid_scale.scaled_width,
                                       video.grid_scale.scaled_height))

            # Calculate actual dimensions to ensure we don't exceed grid boundaries
            actual_height = min(scaled_image.shape[0],
                                self.video_grid_helper.cell_height - video.grid_scale.y_offset)
            actual_width = min(scaled_image.shape[1],
                               self.video_grid_helper.cell_width - video.grid_scale.x_offset)

            # Place image in grid with dimension checks
            try:
                x_start = video.grid_scale.x_start
                y_start = video.grid_scale.y_start

                grid_image[y_start:y_start + actual_height,
                x_start:x_start + actual_width] = scaled_image[:actual_height, :actual_width]
            except ValueError as e:
                logger.error(f"Error placing image in grid: {e}")
                logger.error(f"Grid shape: {grid_image.shape}, "
                             f"Target area: {y_start}:{y_start + actual_height}, "
                             f"{x_start}:{x_start + actual_width}, "
                             f"Scaled image shape: {scaled_image.shape}")
                raise ValueError(f"Error placing image in grid: {e}")

            # Draw grid lines
            cv2.rectangle(grid_image,
                          (x_start, y_start),
                          (x_start + actual_width, y_start + actual_height),
                          color=(0, 255, 0), thickness=2)

            # Draw video name - fixing reference to use scaling_parameters
            cv2.putText(grid_image,
                        str(video_name),
                        (x_start + 10, y_start + 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (255, 255, 255), 2)

        return grid_image
            #
            # if annotate_images:
            #     image = self.image_annotator.annotate_single_image(
            #         image,
            #         click_data=self.data_handler.get_data_by_video_frame(video_index=video_index,
            #                                                              frame_number=frame_number),
            #         active_point=self.data_handler.active_point,
            #     )
            #     if self.show_machine_labels and self.machine_labels_handler is not None and self.machine_labels_annotator is not None:
            #         image = self.machine_labels_annotator.annotate_single_image(
            #             image,
            #             click_data=self.machine_labels_handler.get_data_by_video_frame(video_index=video_index,
            #                                                                            frame_number=frame_number),
            #         )
            #
            #     if zoom_state.scale > 1.0:
            #         # Calculate zoomed dimensions
            #         zoomed_width = int(video.scaling_parameters.scaled_width * zoom_state.scale)
            #         zoomed_height = int(video.scaling_parameters.scaled_height * zoom_state.scale)
            #
            #         # Resize image to zoomed size
            #         zoomed = cv2.resize(image, (zoomed_width, zoomed_height))
            #
            #         # Calculate the relative position within the actual image area
            #         relative_x = (
            #                              zoom_state.center_x - video.scaling_parameters.x_offset) / video.scaling_parameters.scaled_width
            #         relative_y = (
            #                              zoom_state.center_y - video.scaling_parameters.y_offset) / video.scaling_parameters.scaled_height
            #         # Calculate the center point in the zoomed image
            #         center_x = int(relative_x * zoomed_width)
            #         center_y = int(relative_y * zoomed_height)
            #
            #         # Calculate extraction region centered on this point
            #         x1 = max(0, center_x - video.scaling_parameters.scaled_width // 2)
            #         y1 = max(0, center_y - video.scaling_parameters.scaled_height // 2)
            #         x2 = min(zoomed_width, x1 + video.scaling_parameters.scaled_width)
            #         y2 = min(zoomed_height, y1 + video.scaling_parameters.scaled_height)
            #
            #         # Adjust x1,y1 if x2,y2 are at their bounds
            #         if x2 == zoomed_width:
            #             x1 = zoomed_width - video.scaling_parameters.scaled_width
            #         if y2 == zoomed_height:
            #             y1 = zoomed_height - video.scaling_parameters.scaled_height
            #
            #         # Extract visible region
            #         scaled_image = zoomed[y1:y2, x1:x2]
            #
            #     else:
            #         # Normal scaling without zoom
            #         scaled_image = cv2.resize(image,
            #                                   (video.scaling_parameters.scaled_width,
            #                                    video.scaling_parameters.scaled_height))
            #
            #
        #
        # return self.image_annotator.annotate_image_grid(image=grid_image,
        #                                                 active_point=self.data_handler.active_point,
        #                                                 frame_number=frame_number)

    @staticmethod
    def _calculate_scaling_parameters(original_width: int,
                                      original_height: int,
                                      grid_index: int,
                                      video_grid_parameters: VideoGridHelper,
                                      ) -> VideoGridScalingParameters:

        """Calculate scaling parameters for a video to fit in a grid cell."""
        cell_row = video_grid_parameters.get_row_by_index(grid_index)
        cell_column = video_grid_parameters.get_column_by_index(grid_index)
        cell_height = video_grid_parameters.cell_height
        cell_width = video_grid_parameters.cell_width

        # Calculate scale factor preserving aspect ratio
        scale = min(cell_width / original_width, cell_height / original_height)

        scaled_width = int(original_width * scale)
        scaled_height = int(original_height * scale)

        # Calculate offsets to center the video
        x_offset = (cell_width - scaled_width) // 2
        y_offset = (cell_height - scaled_height) // 2

        return VideoGridScalingParameters(
            grid_index=grid_index,
            scale=scale,
            x_offset=x_offset,
            y_offset=y_offset,
            scaled_width=scaled_width,
            scaled_height=scaled_height,
            cell_row=cell_row,
            cell_column=cell_column,
        )

    @classmethod
    def _validate_frame_counts(cls, videos):
        frame_counts = {video_name: video.metadata.frame_count for video_name, video in videos.items()}
        if len(set(frame_counts.values())) > 1:
            logger.error(f"All videos must have the same number of frames: {frame_counts}")
            raise ValueError(f"All videos must have the same number of frames: {frame_counts}")

    def prepare_single_image(self,
                             image: np.ndarray,
                             frame_number: int,
                             scaling_params: VideoGridScalingParameters) -> np.ndarray:
        """Process a video image - resize and add overlays."""
        if image is None:
            return np.zeros(self.video_grid.cell_size + (3,), dtype=np.uint8)

        # Resize image
        resized = cv2.resize(image, (scaling_params.scaled_width, scaling_params.scaled_height))

        # Create padded image
        padded = np.zeros((self.video_grid.cell_height, self.video_grid.cell_width, 3), dtype=np.uint8)
        padded[scaling_params.y_offset:scaling_params.y_offset + scaling_params.scaled_height,
        scaling_params.x_offset:scaling_params.x_offset + scaling_params.scaled_width] = resized

        # Add frame number
        cv2.putText(padded, f"Frame {frame_number}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return padded

    def handle_clicks(self, x: int, y: int, frame_number: int, auto_next_point: bool = False):
        click_data = self.click_handler.process_click(x, y, frame_number)
        if click_data is None:
            return
        self.data_handler.update_dataframe(click_data)

        if auto_next_point:
            self.data_handler.move_active_point_by_index(index_change=1)

    def move_active_point_by_index(self, index_change: int):
        self.data_handler.move_active_point_by_index(index_change=index_change)

    def close(self):
        """Clean up resources."""
        logger.info("VideoHandler closing")
        for video in self.videos.values():
            video.cap.release()

        # while True:
        #     save_data = input("Save data? (yes/no): ")
        #     if save_data.lower() == "yes" or save_data.lower() == "y":
        #         save_path = Path(self.video_folder).parent / "skellyclicker_data"
        #         save_path.mkdir(exist_ok=True, parents=True)
        #         csv_path = save_path / (datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_skellyclicker_output.csv")
        #         self.data_handler.save_csv(output_path=str(csv_path))
        #         break
        #     else:
        #         confirmation = input(
        #             "Confirm your choice: Type 'yes' to prevent data loss or 'no' to delete this session forever (yes/no): ")
        #         if confirmation.lower() == "no" or confirmation.lower() == "n":
        #             logger.info("Data not saved.")
        #             break
