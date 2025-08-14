import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from skellyclicker import VideoNameString, PointNameString
from skellyclicker.core.video_handler.video_models import ClickData, VideoPlaybackState, VideoMetadata, \
    VideoScalingParameters

logger = logging.getLogger(__name__)


class DataHandlerConfig(BaseModel):
    num_frames: int
    video_names: list[str]
    tracked_point_names: list[str]

    @classmethod
    def from_config_file(cls, videos: dict[VideoNameString, VideoPlaybackState], config_path: str):

        with open(file=Path(config_path)) as file:
            config = json.load(file)
        tracked_point_names = config["tracked_point_names"]
        logger.debug(f"Found tracked point names in file: {tracked_point_names}")
        return cls(
            num_frames=next(iter(videos.values())).metadata.frame_count,
            video_names=sorted([video.name for video in videos.values()]),
            tracked_point_names=tracked_point_names,
        )

    @classmethod
    def from_dataframe(cls, dataframe: pd.DataFrame):
        tracked_point_names = []
        seen = set()
        for name in dataframe.columns:
            name = name.removesuffix("_x").removesuffix("_y")
            if name not in seen:
                seen.add(name)
                tracked_point_names.append(name)
        tracked_point_names = list(tracked_point_names)
        logger.debug(f"Found tracked point names in dataframe: {tracked_point_names}")
        return cls(
            num_frames=dataframe.index.get_level_values("frame").max(),
            video_names=sorted(dataframe.index.get_level_values("video").unique().tolist()),
            tracked_point_names=tracked_point_names,
        )





class DataHandler(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    config: DataHandlerConfig
    dataframe: pd.DataFrame
    active_point: PointNameString

    @classmethod
    def from_config(cls, config: DataHandlerConfig):
        dataframe = cls._create_dataframe(config)
        return cls(
            config=config,
            dataframe=dataframe,
            active_point=config.tracked_point_names[0],
        )

    @classmethod
    def from_csv(cls, input_path: str | Path):
        dataframe = pd.read_csv(input_path)
        dataframe["video"] = dataframe["video"].astype(str)
        dataframe = dataframe.set_index(["video", "frame"])

        config = DataHandlerConfig.from_dataframe(dataframe)
        return cls(
            config=config,
            dataframe=dataframe,
            active_point=config.tracked_point_names[0],
        )

    @staticmethod
    def _create_dataframe(config: DataHandlerConfig) -> pd.DataFrame:
        """Create empty dataframe for data, with (Num Videos x Num Frames) rows."""
        column_names = []
        for point_name in config.tracked_point_names:
            column_names.append(f"{point_name}_x")
            column_names.append(f"{point_name}_y")

        video_frame_index = pd.MultiIndex.from_product(
            [config.video_names, range(config.num_frames)], names=["video", "frame"]
        )

        dataframe = pd.DataFrame(np.nan, index=video_frame_index, columns=column_names)

        return dataframe
    
    @property
    def tracked_points(self) -> list[str]:
        return self.config.tracked_point_names

    def set_active_point_by_name(self, point_name: str):
        if point_name not in self.config.tracked_point_names:
            raise ValueError(
                f"Point name {point_name} is not in the list of tracked points: {self.config.tracked_point_names}"
            )
        self.active_point = point_name
        logger.debug(f"Active point set to {self.active_point}")

    def move_active_point_by_index(self, index_change: int):
        current_position = self.config.tracked_point_names.index(self.active_point)
        new_position = (current_position + index_change) % len(
            self.config.tracked_point_names
        )
        self.active_point = self.config.tracked_point_names[new_position]
        logger.debug(f"Active point set to {self.active_point}")

    def update_dataframe(self, click_data: ClickData, point_name: str | None = None):
        video_name = self.config.video_names[click_data.video_index]
        # TODO - NO LIST INDEXING!! We've been burned by this so many times - dicts with video names as keys or something like that would be better
        if point_name is None:
            point_name = self.active_point
        if click_data.x < 0 or click_data.y < 0:
            logger.warning(
                f"Negative click data {click_data} entered for video {video_name}, frame {click_data.frame_number}"
            )
            return
        self.dataframe.loc[
            (video_name, click_data.frame_number), f"{point_name}_x"
        ] = click_data.x
        self.dataframe.loc[
            (video_name, click_data.frame_number), f"{point_name}_y"
        ] = click_data.y

    def clear_current_point(self, video_index: int, frame_number: int):
        video_name = self.config.video_names[video_index]
        self.dataframe.loc[(video_name, frame_number), f"{self.active_point}_x"] = (
            np.nan
        )
        self.dataframe.loc[(video_name, frame_number), f"{self.active_point}_y"] = (
            np.nan
        )
        logger.debug(
            f"Cleared point {self.active_point} for video {video_name}, frame {frame_number}"
        )

    def get_data_by_video_frame(
        self, video_index: int, frame_number: int
    ) -> dict[str, ClickData]:
        video_name = self.config.video_names[video_index]
        video_frame_row = self.dataframe.loc[(video_name, frame_number)]

        # TODO: There is some error in the DLC machine labels that sometimes returns duplicate data, this pulls the first occurence for each row
        if len(video_frame_row.shape) > 1:
            video_frame_row = video_frame_row.iloc[0]
        click_data = {}
        for point_name in self.config.tracked_point_names:
            x = video_frame_row[f"{point_name}_x"]
            y = video_frame_row[f"{point_name}_y"]
            if not np.isnan(x) and not np.isnan(y):
                click_data[point_name] = ClickData(
                    video_index=video_index,
                    frame_number=frame_number,
                    video_x=int(x),
                    video_y=int(y),
                    window_x=int(x),
                    window_y=int(y),
                )
        return click_data
    
    def get_data_by_video_name_and_frame(
        self, video_name: str, frame_number: int
    ) -> dict[str, ClickData]:
        video_index = self.config.video_names.index(video_name)
        video_frame_row = self.dataframe.loc[(video_name, frame_number)]

        # TODO: There is some error in the DLC machine labels that sometimes returns duplicate data, this pulls the first occurence for each row
        if len(video_frame_row.shape) > 1:
            video_frame_row = video_frame_row.iloc[0]
        click_data = {}
        for point_name in self.config.tracked_point_names:
            x = video_frame_row[f"{point_name}_x"]
            y = video_frame_row[f"{point_name}_y"]
            if not np.isnan(x) and not np.isnan(y):
                click_data[point_name] = ClickData(
                    video_index=video_index,
                    frame_number=frame_number,
                    video_x=int(x),
                    video_y=int(y),
                    window_x=int(x),
                    window_y=int(y),
                )
        return click_data

    def get_nonempty_frames(self) -> list[int]:
        mask = self.dataframe.iloc[:, 2:].notna().any(axis=1)
        nonempty_dataframe = self.dataframe[mask]
        nonempty_frames = nonempty_dataframe.index.get_level_values("frame").unique()
        return sorted(nonempty_frames.tolist())

    def save_csv(self, output_path: str | Path):
        self.dataframe.to_csv(output_path)
        logger.info(f"Saved csv data to {output_path}")

    def save_parquet(self, output_path: str | Path):
        # TODO: Add some useful metadata here?
        self.dataframe.to_parquet(output_path)
        logger.info(f"Saved parquet data to {output_path}")


if __name__ == "__main__":
    import cv2

    video_paths = Path(
        Path.home()
        / "freemocap_data/recording_sessions/freemocap_test_data/synchronized_videos"
    ).glob("*.mp4")
    config_file_path = Path("../../../tracked_points.json")

    _videos = []
    image_counts = set()

    for video_path in video_paths:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        metadata = VideoMetadata(
            path=str(video_path),
            name=video_path.name,
            width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            frame_count=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        )

        image_counts.add(metadata.frame_count)

        scaling_params = VideoScalingParameters(
            scale=1.0,
            x_offset=0,
            y_offset=0,
            scaled_width=metadata.width,
            scaled_height=metadata.height,
            original_width=metadata.width,
            original_height=metadata.height,
        )

        _videos.append(
            VideoPlaybackState(
                metadata=metadata, cap=cap, grid_scale=scaling_params
            )
        )
    handler_config = DataHandlerConfig.from_config_file(
        videos=_videos, config_path=config_file_path
    )
    handler = DataHandler.from_config(handler_config)

    click_data = ClickData(
        window_x=100,
        window_y=100,
        video_x=120,
        video_y=100,
        frame_number=0,
        video_index=0,
    )
    handler.update_dataframe(click_data)
    handler.set_active_point_by_name("nose")
    click_data = ClickData(
        window_x=100,
        window_y=100,
        video_x=70,
        video_y=80,
        frame_number=221,
        video_index=2,
    )
    handler.update_dataframe(click_data)
    logger.debug(handler.dataframe)
    data = handler.get_data_by_video_frame(video_index=0, frame_number=0)
    logger.debug(f"type(data): {type(data)}, data: {data}")
    handler.dataframe.to_csv("test.csv")
