"""
Configuration classes for DeepLabCut pipeline
---------------------------------------------
Classes to organize and manage configuration settings for the DeepLabCut pipeline.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union
from deeplabcut.utils import auxiliaryfunctions


@dataclass
class SimpleDeeplabcutProjectConfig:
    """Configuration for project setup"""

    # Basic project information
    name: str
    experimenter: str = "human"
    working_directory: str|None = None

    # Anatomical configuration
    bodyparts: List[str] = field(default_factory=list)
    skeleton: list[list[str]]|None = None

    def __post_init__(self):
        if isinstance(self.working_directory, str):
            self.working_directory = self.working_directory
        elif self.working_directory is None:
            self.working_directory = str(Path.cwd())

        Path(self.working_directory).mkdir(exist_ok=True, parents=True)
    
    @classmethod
    def from_deeplabcut_config(cls, deeplabcut_config: dict) -> "SimpleDeeplabcutProjectConfig":
        return cls(
            name=deeplabcut_config["Task"],
            experimenter=deeplabcut_config["scorer"],
            working_directory=deeplabcut_config["project_path"],
            bodyparts=deeplabcut_config["bodyparts"],
            skeleton=deeplabcut_config["skeleton"],
        )

    @classmethod
    def from_deeplabcut_config_yaml(cls, deeplabcut_config_path: str | Path) -> "SimpleDeeplabcutProjectConfig":
        config = auxiliaryfunctions.read_config(deeplabcut_config_path)

        return cls.from_deeplabcut_config(config)


@dataclass
class SkellyclickerDataConfig:
    """Configuration for data processing"""

    folder_of_videos: Path
    labels_csv_path: Path

    def __post_init__(self):
        if isinstance(self.folder_of_videos, str):
            self.folder_of_videos = Path(self.folder_of_videos)
        if isinstance(self.labels_csv_path, str):
            self.labels_csv_path = Path(self.labels_csv_path)

    @classmethod
    def from_config(cls, config: dict) -> "SkellyclickerDataConfig":
        return cls(
            folder_of_videos=config["skellyclicker_folder_of_videos"],
            labels_csv_path=config["skellyclicker_labels_csv_path"],
        )

    @classmethod
    def from_config_yaml(cls, config_path: str | Path) -> "SkellyclickerDataConfig":
        config = auxiliaryfunctions.read_config(config_path)

        return cls.from_config(config)

    def update_config_yaml(self, config_path: str | Path):
        auxiliaryfunctions.edit_config(
            config_path,
            {
                "skellyclicker_folder_of_videos": str(self.folder_of_videos),
                "skellyclicker_labels_csv_path": str(self.labels_csv_path),
            },
        )


@dataclass
class TrainingConfig:
    """Configuration for model training"""

    # Network settings
    model_type: str = "resnet_50"

    # Training settings
    epochs: int = 200  # this is the new equivalent of 'maxiters' for PyTorch (200 is their default)
    save_epochs: int = 20  # this is the new equivalent of 'save_iters' for PyTorch
    batch_size: int = 1  # this seems to be similar to batch/multi processing (higher number = faster if your gpu can handle it?)
    
    @classmethod
    def from_config(cls, config: dict, epochs: int = 200, save_epochs: int = 20) -> "TrainingConfig":
        return cls(
            model_type=config["default_net_type"],
            epochs=config.get("skellyclicker_epochs", epochs),
            save_epochs=config.get("skellyclicker_save_epochs", save_epochs),
            batch_size=config["batch_size"],
        )
    
    @classmethod
    def from_config_yaml(cls, config_path: str | Path, epochs: int = 200, save_epochs: int = 20) -> "TrainingConfig":
        config = auxiliaryfunctions.read_config(config_path)

        return cls.from_config(config, epochs, save_epochs)
    
    def update_config_yaml(self, config_path: str | Path):
        auxiliaryfunctions.edit_config(
            config_path,
            {
                "default_net_type": self.model_type,
                "skellyclicker_epochs": self.epochs,
                "skellyclicker_save_epochs": self.save_epochs,
                "batch_size": self.batch_size,
            },
        )