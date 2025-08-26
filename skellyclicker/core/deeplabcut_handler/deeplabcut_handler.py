import logging
import deeplabcut

from deeplabcut import DEBUG
from deeplabcut.utils import auxiliaryfunctions
from pathlib import Path
import pandas as pd
from pydantic import BaseModel

from skellyclicker.core.deeplabcut_handler.create_deeplabcut.create_deeplabcut_config import (
    create_new_deeplabcut_project,
)
from skellyclicker.core.deeplabcut_handler.create_deeplabcut.create_deeplabcut_project_data import (
    fill_in_labelled_data_folder,
)
from skellyclicker.core.deeplabcut_handler.create_deeplabcut.deelabcut_project_config import (
    DeeplabcutTrainingConfig,
)


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
        deeplabcut.create_training_dataset(self.project_config_path)

        logger.info("Training model...")
        logger.info(f"With config: epochs={training_config.epochs}, save epochs={training_config.save_epochs}, batch_size={training_config.batch_size}")
        deeplabcut.train_network(
            self.project_config_path,
            epochs=training_config.epochs,
            save_epochs=training_config.save_epochs,
            batch_size=training_config.batch_size,
            pytorch_cfg_updates={
                "runner.optimizer.params.lr": 0.0001
            }
        )

    def analyze_videos(
        self,
        video_paths: list[str],
        annotate_videos: bool = False,
        filter_videos: bool = True,
    ) -> str:
        config = auxiliaryfunctions.read_config(self.project_config_path)
        output_folder = (
            Path(config["project_path"])
            / "model_outputs"
            / f"model_outputs_iteration_{config['iteration']}"
        )
        output_folder.mkdir(parents=True, exist_ok=True)

        deeplabcut.analyze_videos(
            config=str(self.project_config_path),
            videos=video_paths,
            videotype=".mp4",
            save_as_csv=True,
            destfolder = str(output_folder)
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


        if annotate_videos:
            print(
                f"Annotating videos {video_paths}, saving to {output_folder}"
            )
            deeplabcut.create_labeled_video(
                config=self.project_config_path,
                videos=video_paths,
                videotype=".mp4",
                destfolder=str(output_folder),
                filtered=filter_videos,
            )
        else:
            print("Skipping video annotation")

        deeplabcut.plot_trajectories(config=self.project_config_path, videos=video_paths, filtered=filter_videos, destfolder=str(output_folder))

        csv_path = output_folder / f"skellyclicker_machine_labels_iteration_{config['iteration']}.csv"

        video_folders = set(Path(video_path).parent for video_path in video_paths)
        if len(video_folders) > 1:
            raise ValueError("All videos must be in the same folder for training")

        self.merge_csvs_for_skellyclicker(
            csv_folder_path=str(output_folder),
            output_path=str(csv_path),
            filtered=filter_videos,
        )

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
