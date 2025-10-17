import logging
import math
import cv2
import deeplabcut
from deeplabcut import DEBUG
from deeplabcut.utils import auxiliaryfunctions
from multiprocessing import Pool
from pathlib import Path
import pandas as pd
from pydantic import BaseModel
from time import perf_counter_ns

from skellyclicker.core.click_data_handler.data_handler import DataHandler
from skellyclicker.core.video_handler.image_annotator import ImageAnnotator, ImageAnnotatorConfig
from skellyclicker.core.deeplabcut_handler.create_deeplabcut.create_deeplabcut_config import (
    create_new_deeplabcut_project,
)
from skellyclicker.core.deeplabcut_handler.create_deeplabcut.create_deeplabcut_project_data import (
    fill_in_labelled_data_folder,
)
from skellyclicker.core.deeplabcut_handler.create_deeplabcut.deelabcut_project_config import (
    DeeplabcutTrainingConfig,
)
from skellyclicker.core.deeplabcut_handler.analyze_videos_dlc import analyze_videos_dlc


logger = logging.getLogger(__name__)


class PointConnection(BaseModel):
    parent: str
    child: str

    @classmethod
    def from_tuple(cls, points: tuple[str, str]):
        return cls(parent=points[0], child=points[1])

    @property
    def as_tuple(self) -> tuple[str, str]:
        return self.parent, self.child

    @property
    def as_list(self) -> list[str]:
        return list(self.as_tuple)


class DeeplabcutHandler(BaseModel):
    project_name: str
    project_config_path: str
    iteration: int
    tracked_point_names: list[str]
    connections: list[PointConnection] | None

    @classmethod
    def create_deeplabcut_project(
        cls,
        project_name: str,
        project_parent_directory: str,
        tracked_point_names: list[str],
        connections: list[PointConnection] | None = None,
    ):
        logger.info("Creating deeplabcut project structure...")

        if connections is None:
            connections = []
        return cls(
            project_name=project_name,
            connections=connections,
            iteration=0,
            tracked_point_names=tracked_point_names,
            project_config_path=create_new_deeplabcut_project(
                project_name=project_name,
                project_parent_directory=project_parent_directory,
                bodyparts=tracked_point_names,
                skeleton=[connection.as_list for connection in connections],
            ),
        )

    @classmethod
    def load_deeplabcut_project(cls, project_config_path: str):
        logger.info(f"Loading deeplabcut project from config: {project_config_path}")
        config = auxiliaryfunctions.read_config(project_config_path)

        return cls(
            project_name=config["Task"],
            tracked_point_names=config["bodyparts"],
            iteration=config["iteration"],
            connections=[
                PointConnection.from_tuple(connection)
                for connection in config["skeleton"]
            ],
            project_config_path=project_config_path,
        )

    def _bump_iteration(self):
        config = auxiliaryfunctions.read_config(self.project_config_path)

        shuffles_path = Path(self.project_config_path).parent / "training-datasets"
        results_path = Path(self.project_config_path).parent / "dlc-models"

        # bump the iteration in the config file
        config["iteration"] += 1
        iteration_count = int(config["iteration"])
        logger.info(f"Bumped iteration to: {iteration_count}")

        # Create common subdirectories for training-datasets
        iteration_path = shuffles_path / f"iteration-{iteration_count}"
        iteration_path.mkdir(parents=True, exist_ok=bool(DEBUG))
        logger.info(f"Created training dataset directory: {iteration_path}")

        # Create common subdirectories for dlc-models
        model_iteration_path = results_path / f"iteration-{iteration_count}"
        model_iteration_path.mkdir(parents=True, exist_ok=bool(DEBUG))
        logger.info(f"Created model directory: {model_iteration_path}")

        auxiliaryfunctions.write_config(self.project_config_path, config)
        self.iteration = iteration_count
        logger.info(f"Saved updated config file: {self.project_config_path}")

    def train_model(
        self,
        labels_csv_path: str,
        video_paths: list[str],
        training_config: DeeplabcutTrainingConfig | None = None,
    ):
        if training_config is None:
            training_config = DeeplabcutTrainingConfig()

        video_folders = set(Path(video_path).parent for video_path in video_paths)
        if len(video_folders) > 1:
            raise ValueError("All videos must be in the same folder for training")
        video_folder = video_folders.pop()

        parent_directory = Path(self.project_config_path).parent

        if (
            parent_directory / "dlc-models-pytorch" / f"iteration-{self.iteration}"
        ).exists():
            logger.info(
                "Model detected for current iteration, bumping to next iteration"
            )
            self._bump_iteration()

        logger.info("Processing labeled frames...")
        fill_in_labelled_data_folder(
            path_to_videos_for_training=str(video_folder),
            path_to_dlc_project_folder=str(parent_directory),
            path_to_image_labels_csv=labels_csv_path,
        )

        logger.info("Creating training dataset...")
        deeplabcut.create_training_dataset(self.project_config_path, net_type='resnet_50')
        # deeplabcut.create_training_model_comparison(self.project_config_path, net_types=["resnet_50", "rtmpose_x"])


        batch_size = training_config.batch_size
        learning_rate = training_config.learning_rate
        if batch_size > 1:
            learning_rate *= math.floor(math.sqrt(batch_size))
            training_config.learning_rate = learning_rate
            print(f"Adjusted default learning rate to scale with square root of batch size")
            print("See https://stackoverflow.com/questions/64105986/in-2020-what-is-the-optimal-way-to-train-a-model-in-pytorch-on-more-than-one-gpu")

        pytorch_cfg_updates = {
            "runner.optimizer.params.lr": training_config.learning_rate
        }
        if training_config.hflip_augmentation:
            pytorch_cfg_updates["data.train.hflip"] = True
        logger.info("Training model...")
        logger.info(f"With config: epochs={training_config.epochs}, save epochs={training_config.save_epochs}, batch_size={training_config.batch_size}, learning_rate={training_config.learning_rate}")
        start_time = perf_counter_ns()
        deeplabcut.train_network(
            self.project_config_path,
            epochs=training_config.epochs,
            save_epochs=training_config.save_epochs,
            batch_size=training_config.batch_size,
            pytorch_cfg_updates=pytorch_cfg_updates
        )
        end_time = perf_counter_ns()
        print(f"Model training took {(end_time-start_time)/1e9} seconds over {training_config.epochs} epochs ({(end_time-start_time)/(1e9*training_config.epochs)} s per epoch)")

    def analyze_videos(
        self,
        video_paths: list[str],
        output_folder: str | Path,
        annotate_videos: bool = False,
        filter_videos: bool = True,
    ) -> str:
        config = auxiliaryfunctions.read_config(self.project_config_path)
        Path(output_folder).mkdir(parents=True, exist_ok=True)

        analyze_videos_dlc(
            config=str(self.project_config_path),
            videos=video_paths,
            videotype=".mp4",
            save_as_csv=True,
            destfolder = str(output_folder),
            batch_size=8,  # 16 is too high for 5 mocap videos
            multiprocess=False
        )

        if filter_videos:
            deeplabcut.filterpredictions(
                str(self.project_config_path),
                video_paths,
                videotype=".mp4",
                filtertype="median",
                windowlength=5,
                destfolder=str(output_folder),
            )

        deeplabcut.plot_trajectories(config=self.project_config_path, videos=video_paths, filtered=filter_videos, destfolder=str(output_folder))

        csv_path = Path(output_folder) / f"skellyclicker_machine_labels_iteration_{config['iteration']}.csv"

        video_folders = set(Path(video_path).parent for video_path in video_paths)
        if len(video_folders) > 1:
            raise ValueError("All videos must be in the same folder for training")

        self.merge_csvs_for_skellyclicker(
            csv_folder_path=str(output_folder),
            output_path=str(csv_path),
            filtered=filter_videos,
        )

        if annotate_videos:
            self.annotate_videos(
                output_path=str(output_folder),
                csv_path=str(csv_path),
                video_paths=[Path(video) for video in video_paths]
            )
        else:
            print("Skipping video annotation")

        return str(csv_path)

    def merge_csvs_for_skellyclicker(
        self, csv_folder_path: str | Path, output_path: str | Path, filtered: bool = False
    ):
        dataframe_list = []
        csv_folder_path = Path(csv_folder_path)
        if filtered:
            csv_paths = csv_folder_path.glob("*_filtered.csv")
        else:
            csv_paths = set(csv_folder_path.glob("*.csv")).difference(set(csv_folder_path.glob("*_filtered.csv")))
        if not csv_paths:
            raise FileNotFoundError(
                f"No matching CSV files found in {csv_folder_path}. Please check the path."
            )
        csv_paths = set(csv_paths).difference(set(csv_folder_path.glob(".csv")))
        csv_paths = sorted(list(csv_paths))
        for csv in csv_paths:
            df = pd.read_csv(csv)

            video_name = Path(csv).name.split("DLC_")[0]

            bodyparts = df.iloc[0, :].unique()[1:]

            column_names = ["frame"]
            for bodypart in bodyparts:
                column_names.extend(
                    [f"{bodypart}_x", f"{bodypart}_y", f"{bodypart}_likelihood"]
                )

            df.columns = column_names

            # remove first two rows
            df = df.iloc[2:, :]
            # TODO: consider filtering for confidence

            df = df.drop(columns=[f"{bodypart}_likelihood" for bodypart in bodyparts])

            df["video"] = video_name

            # set frames and video as multi index
            df = df.set_index(["video", "frame"])

            print(df.head())

            dataframe_list.append(df)

        df = pd.concat(dataframe_list)
        print(df)

        df.to_csv(output_path)
        print(f"Saved skellyclicker compatible CSV to {output_path}")

    def annotate_videos(self, output_path: str | Path, video_paths: list[Path], csv_path: str | Path):
        print(
            f"Annotating videos {video_paths}, saving to {output_path}"
        )
        args = [
            (output_path, csv_path, video) for video in video_paths
        ]
        with Pool(processes=len(video_paths)) as pool:
            pool.starmap(self.annotate_single_video, args)

    def annotate_single_video(self, output_path: str | Path, csv_path: str | Path, video: Path):
        data_handler = DataHandler.from_csv(csv_path)
        annotator_config = ImageAnnotatorConfig(
                marker_thickness=3,
                show_names=False,
                tracked_points=sorted(data_handler.tracked_points),
                show_clicks=False,
                show_help=False
            )
        image_annotator = ImageAnnotator(config=annotator_config)


        video_name = video.stem
        cap = cv2.VideoCapture(str(video))

        framerate = cap.get(cv2.CAP_PROP_FPS)
        framesize = (
                int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            )
        fourcc = cv2.VideoWriter.fourcc(*"mp4v")  # need to deal with higher frame rates
        print(f"writing video to {str(Path(output_path) / video.name)}")

        video_writer_object = cv2.VideoWriter(
                str(Path(output_path) / video.name), fourcc, round(framerate, 2), framesize
            )

        frame_number = -1
        while True:
            ret, frame = cap.read()
            frame_number += 1
            if not ret:
                print(f"failed to read frame {frame_number}")
                break

            click_data = data_handler.get_data_by_video_name_and_frame(video_name=video_name, frame_number=frame_number)

            annotated_frame = image_annotator.annotate_single_image(image=frame, click_data=click_data)
            video_writer_object.write(annotated_frame)
        video_writer_object.release()
        cap.release()
