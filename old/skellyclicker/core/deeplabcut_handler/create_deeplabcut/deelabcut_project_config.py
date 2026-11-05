from dataclasses import dataclass
from pathlib import Path
from pydantic import BaseModel
from deeplabcut.utils import auxiliaryfunctions



class SkellyClickerDataConfig(BaseModel):
    """Configuration for data processing"""

    video_paths: list[str]
    click_data_csv_path: str


    @classmethod
    def from_config(cls, config: dict) -> "SkellyClickerDataConfig":
        return cls(
            video_paths=config["skellyclicker_folder_of_videos"],
            click_data_csv_path=config["skellyclicker_labels_csv_path"],
        )

    @classmethod
    def from_config_yaml(cls, config_path: str ) -> "SkellyClickerDataConfig":
        if not Path(config_path).is_file() and config_path.endswith(".yaml"):
            raise ValueError(f"`{config_path} is not a path to a valid yaml file")

        config = auxiliaryfunctions.read_config(config_path)

        return cls.from_config(config)

    def update_config_yaml(self, config_path: str | Path):
        auxiliaryfunctions.edit_config(
            config_path,
            {
                "skellyclicker_video_paths": str(self.video_paths),
                "skellyclicker_labels_csv_path": str(self.click_data_csv_path),
            },
        )


class DeeplabcutTrainingConfig(BaseModel):
    """Configuration for model training"""

    # Network settings
    model_type: str = "resnet_50"

    # Augmentation settings
    hflip_augmentation: bool = False

    # Training settings
    epochs: int = 200  # this is the new equivalent of 'maxiters' for PyTorch (200 is their default)
    save_epochs: int = 20  # this is the new equivalent of 'save_iters' for PyTorch
    batch_size: int = 1  # this seems to be similar to batch/multi processing (higher number = faster if your gpu can handle it?)
    learning_rate: float = 0.0001  # DLC default, changing this could help with sessions that won't train
    
    @classmethod
    def from_config(cls, config: dict, epochs: int = 200, save_epochs: int = 20):
        return cls(
            model_type=config["default_net_type"],
            epochs=config.get("skellyclicker_epochs", epochs),
            save_epochs=config.get("skellyclicker_save_epochs", save_epochs),
            batch_size=config["batch_size"],
        )
    
    @classmethod
    def from_config_yaml(cls, config_path: str | Path, epochs: int = 200, save_epochs: int = 20):
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