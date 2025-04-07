import shutil
import logging
from pathlib import Path
from deeplabcut import DEBUG
import deeplabcut
from deeplabcut.utils import auxiliaryfunctions

from scholl_lab.dlc_utils.create_dlc_project_data import fill_in_labelled_data_folder
from scholl_lab.dlc_utils.project_config import DataConfig, ProjectConfig, TrainingConfig

logger = logging.getLogger(__name__)


def iterate_model(
    config_path: str | Path,
    clicker_csv_path: str | Path,
    training_config: TrainingConfig | None = None,
) -> None:
    config = auxiliaryfunctions.read_config(config_path)
    project = ProjectConfig.from_config(config)
    data = DataConfig.from_config(config)
    if training_config:
        training = training_config
    else:
        training = TrainingConfig.from_config(config)

    data.labels_csv_path = Path(clicker_csv_path)
    
    project_path = Path(project.working_directory)

    shuffles_path = project_path / "training-datasets"
    results_path = project_path / "dlc-models"

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

    auxiliaryfunctions.write_config(config_path, config)
    data.update_config_yaml(config_path)
    logger.info(f"Saved updated config file: {config_path}")


    logger.info("Processing labeled frames...")
    labeled_frames = fill_in_labelled_data_folder(
        path_to_videos_for_training=Path(data.folder_of_videos),
        path_to_dlc_project_folder=project_path,
        path_to_image_labels_csv=Path(data.labels_csv_path),
        scorer_name=project.experimenter,
    )

    # make new training dataset
    logger.info("Creating training dataset...")
    deeplabcut.create_training_dataset(
        config=config_path,
    )

    # rerun model
    logger.info("Training network...")
    deeplabcut.train_network(
        config=config_path,
        epochs=training.epochs,
        save_epochs=training.save_epochs,
        batch_size=training.batch_size
    )


if __name__ == "__main__":
    config_path = "/Users/philipqueen/DLCtest/freemocap_sample_data_test_philip_20250402/config.yaml"
    clicker_csv_path = "/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/skellyclicker_data/2025-04-03_12-15-39_skellyclicker_output.csv"

    iterate_model(config_path=config_path, clicker_csv_path=clicker_csv_path)
