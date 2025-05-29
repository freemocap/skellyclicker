import logging
from pathlib import Path
from pydantic import BaseModel, ValidationError

from skellyclicker.app.app_state import AppState
from skellyclicker.core.deeplabcut_handler.create_deeplabcut.deelabcut_project_config import DeeplabcutTrainingConfig
from skellyclicker.core.deeplabcut_handler.deeplabcut_handler import DeeplabcutHandler
from skellyclicker.core.video_handler.video_viewer import VideoViewer
from skellyclicker.system.files_and_folder_names import DEEPLABCUT_CONFIG_FILE_NAME

logger = logging.getLogger(__name__)

class SkellyclickerApp(BaseModel):
    app_state: AppState
    video_viewer: VideoViewer | None = None
    deeplabcut_handler: DeeplabcutHandler | None = None

    @classmethod
    def create(cls, app_state: AppState | None = None) -> "SkellyclickerApp":
        if app_state is None:
            app_state = AppState()
 
        class_instance = cls(app_state=app_state)

        if app_state.project_path:
            class_instance.load_deeplabcut_project(
                project_path=app_state.project_path
            )

        return class_instance

    def get_app_state(self) -> AppState:
        """
        Returns the current application state.
        """
        return self.app_state

    def get_dlc_iteration(self) -> int:
        """
        Returns the current DeepLabCut iteration.
        """
        if self.deeplabcut_handler is None:
            logger.warning("No DeepLabCut handler initialized, returning iteration 0")
            return 0
        return self.deeplabcut_handler.iteration

    def load_deeplabcut_project(self, project_path: str) -> None:
        if not Path(project_path).exists():
            logger.error(f"Project path does not exist: {project_path}")
            return
        
        if not Path(project_path).is_dir():
            logger.error(f"Project path is not a directory: {project_path}")
            return

        if not (Path(project_path) / DEEPLABCUT_CONFIG_FILE_NAME).exists():
            logger.error(
                f"DeepLabCut config file not found in project path: {project_path}"
            )
            return

        self.app_state.project_path = project_path
        self.deeplabcut_handler = DeeplabcutHandler.load_deeplabcut_project(
            project_config_path=str(
                Path(project_path) / DEEPLABCUT_CONFIG_FILE_NAME
            )
        )

        logger.info(f"DeepLabCut project loaded from: {project_path}")

    def create_deeplabcut_project(self, project_name: str, project_path: str) -> None:
        if (
            self.app_state.tracked_point_names is None
            or len(self.app_state.tracked_point_names) == 0
        ):
            logger.info(
                "No tracked point names available, load and label videos before creating deeplabcut project"
            )
            return 

        if not Path(project_path).exists():
            Path(project_path).mkdir(parents=True, exist_ok=True)
        if not Path(project_path).is_dir():
            logger.error(f"Project path is not a directory: {project_path}")
            return

        full_project_path = Path(project_path) / project_name
        self.app_state.project_path = str(full_project_path)


        self.deeplabcut_handler = DeeplabcutHandler.create_deeplabcut_project(
            project_name=project_name,
            project_parent_directory=project_path,
            tracked_point_names=self.app_state.tracked_point_names,
            connections=None,  # TODO: Handle connections somehow
        )


        logger.info(f"Creating new deeplabcut project: {full_project_path}")

    def load_videos(self, video_paths: list[str]) -> None:
        self.app_state.video_files = video_paths
        self.open_videos()

    def load_labels_csv(self, csv_path: str) -> None:
        if (
            csv_path
            and Path(csv_path).exists()
            and Path(csv_path).is_file()
            and Path(csv_path).suffix == ".csv"
        ):
            self.app_state.csv_saved_path = csv_path
            logger.info(f"Labels CSV loaded from: {csv_path}")
        else:
            logger.warning("Invalid CSV file selected or file does not exist")

    def load_machine_labels_csv(self, machine_labels_path: str) -> None:
        if (
            machine_labels_path
            and Path(machine_labels_path).exists()
            and Path(machine_labels_path).is_file()
            and Path(machine_labels_path).suffix == ".csv"
        ):
            self.app_state.machine_labels_path = machine_labels_path
            logger.info(f"Machine labels CSV loaded from: {machine_labels_path}")
        else:
            logger.warning("Invalid CSV file selected or file does not exist")

    def clear_labels_csv(self) -> None:
        logger.info(f"Clearing labels CSV {self.app_state.csv_saved_path}")
        self.app_state.csv_saved_path = None
        logger.info("Labels CSV cleared")

    def clear_machine_labels_csv(self) -> None:
        logger.info(f"Clearing machine labels CSV {self.app_state.machine_labels_path}")
        self.app_state.machine_labels_path = None
        logger.info("Machine labels CSV cleared")

    def open_videos(self) -> None:
        if self.app_state.video_files:
            logger.info(f"Videos loaded: {len(self.app_state.video_files)} files")
            if self.video_viewer:
                logger.info("Stopping previous video viewer")
                self.video_viewer.stop()
                logger.info("Previous video viewer stopped")

            if self.app_state.csv_saved_path:
                self.video_viewer = VideoViewer.from_videos(
                    video_paths=self.app_state.video_files,
                    data_handler_path=self.app_state.csv_saved_path,
                    machine_labels_path=self.app_state.machine_labels_path,
                )
            else:
                self.video_viewer = VideoViewer.from_videos(
                    video_paths=self.app_state.video_files,
                    machine_labels_path=self.app_state.machine_labels_path,
                )
            self.app_state.tracked_point_names = (
                self.video_viewer.video_handler.data_handler.config.tracked_point_names
            )
            self.app_state.frame_count = self.video_viewer.video_handler.frame_count
            self.video_viewer.on_complete = self.video_viewer_on_complete
            logger.info("Launching video viewer thread")
            self.video_viewer.launch_video_thread()
        else:
            raise RuntimeError("No video files have been loaded")

    def video_viewer_on_complete(self) -> None:
        if self.video_viewer is None:
            logger.info("Video viewer closed while not initialized")
            return
        # TODO: How to handle interactivity here?
        save_data = True
        save_path = self.video_viewer.video_handler.close(save_data=save_data)

        if save_data and save_path:
            self.app_state.csv_saved_path = save_path
            self.update_progress()
            logger.info(f"Data saved to: {save_path}")

        self.video_viewer = None

    def train_model(self) -> None:
        if not self.app_state.project_path:
            logger.warning("No Project, please load or create a project first")
            return
        logger.info("Training model...")
        if self.deeplabcut_handler is None:
            logger.warning(
                "No DeepLabCut Handler, DeepLabCut handler must be initialized before training a model"
            )
            return
        if not self.app_state.video_files:
            logger.warning(
                "No videos: attempted to train model without loading videos, must load videos and label before training",
            )
            return
        if not self.app_state.csv_saved_path:
            logger.warning(
                "No Data: attempted to train model without saving data, must label videos before training",
            )
            return
        training_config = DeeplabcutTrainingConfig(
            epochs=self.app_state.training_epochs,
            save_epochs=self.app_state.training_save_epochs,
            batch_size=self.app_state.training_batch_size,
        )
        self.deeplabcut_handler.train_model(
            labels_csv_path=self.app_state.csv_saved_path,
            video_paths=self.app_state.video_files,
            training_config=training_config,
        )
        logger.info("Model completed training")

    def analyze_training_videos(self) -> None:
        if self.app_state.video_files is None or len(self.app_state.video_files) == 0:
            logger.warning("No training videos, please load training videos before analyzing")
            return
        self.analyze_videos(video_paths=self.app_state.video_files, copy_to_machine_labels=True)

    def analyze_videos(self, video_paths: list[str], copy_to_machine_labels: bool) -> None:
        if not self.app_state.project_path:
            logger.warning("No Project, please load or create a project first")
            return
        logger.info("Analyzing videos...")
        if self.deeplabcut_handler is None:
            logger.warning(
                "No DeepLabCut Handler, DeepLabCut handler must be initialized before analyzing videos"
            )
            return
        
        if video_paths is None or len(video_paths) == 0:
            logger.warning("No video paths provided")
            return

        machine_labels_path = self.deeplabcut_handler.analyze_videos(
            video_paths=video_paths,
            annotate_videos=self.app_state.annotate_videos,
            filter_videos=self.app_state.filter_predictions,
        )

        if copy_to_machine_labels:
            self.app_state.machine_labels_path = machine_labels_path
        logger.info("Videos analyzed")

    def set_save_path(self, file_path: str) -> None:
        self.app_state.csv_saved_path = file_path
        logger.info(f"New save path set to: {file_path}")

    def save_session(self, output_path: str) -> None:
        output_directory = (
            Path(self.app_state.session_saved_path).parent
            if self.app_state.session_saved_path
            else None
        )
        output_filename = (
            Path(self.app_state.session_saved_path).name
            if self.app_state.session_saved_path
            else None
        )

        json_data = self.app_state.model_dump_json(indent=4)

        if output_path is None or output_path == "":
            logger.info("No valid path selected, session not saved")
            return

        with open(output_path, "w") as f:
            f.write(json_data)

        logger.info(f"Session successfully saved to: {output_path}")

    def load_session(self, json_file: str) -> None:
        if json_file is None or json_file == "":
            logger.warning(f"No valid file selected, session not loaded. File: {json_file}")
            return
        with open(json_file, "r") as f:
            json_data = f.read()

        try:
            self.app_state = AppState.model_validate_json(json_data)
            self.app_state.session_saved_path = json_file
        except ValidationError as e:
            logger.info(f"Error loading session: {e}")
            return

        if self.deeplabcut_handler:
            logger.info(
                "WARNING: Project loaded while deeplabcut handler already initialized, closing deeplabcut project"
            )
        if self.app_state.project_path:
            self.deeplabcut_handler = DeeplabcutHandler.load_deeplabcut_project(
                project_config_path=str(
                    Path(self.app_state.project_path) / DEEPLABCUT_CONFIG_FILE_NAME
                )
            )
        else:
            self.deeplabcut_handler = None

        logger.info(f"Session successfully loaded from: {json_file}")

    def toggle_autosave(self) -> None:
        self.app_state.auto_save = not self.app_state.auto_save
        logger.info(f"Auto-save set to: {self.app_state.auto_save}")

    def toggle_show_help(self) -> None:
        self.app_state.show_help = not self.app_state.show_help
        logger.info(f"Show help set to: {self.app_state.show_help}")

    def toggle_annotate_videos(self) -> None:
        self.app_state.annotate_videos = not self.app_state.annotate_videos
        logger.info(f"Annotate videos set to: {self.app_state.annotate_videos}")

    def toggle_filter_predictions(self) -> None:
        self.app_state.filter_predictions = not self.app_state.filter_predictions
        logger.info(f"Filter predictions set to: {self.app_state.filter_predictions}")

    def set_training_epochs(self, training_epochs: int) -> None:
        if training_epochs < 1:
            logger.warning("Training epochs must be at least 1")
            return
        self.app_state.training_epochs = training_epochs
        logger.info(f"Training epochs set to: {self.app_state.training_epochs}")

    def set_training_save_epochs(self, save_epochs: int) -> None:
        if save_epochs < 1:
            logger.warning("Save epochs must be at least 1")
            return
        self.app_state.training_save_epochs = save_epochs
        logger.info(f"Training save epochs set to: {self.app_state.training_save_epochs}")

    def set_training_batch_size(self, batch_size: int) -> None:
        if batch_size < 1:
            logger.warning("Batch size must be at least 1")
            return
        self.app_state.training_batch_size = batch_size
        logger.info(f"Training batch size set to: {self.app_state.training_batch_size}")

    def update_progress(self) -> None:
        if self.video_viewer:
            total_frames = self.video_viewer.video_handler.frame_count
            labeled_frames = self.video_viewer.video_handler.data_handler.get_nonempty_frames()
            self.app_state.frame_count = total_frames
            self.app_state.labeled_frames = labeled_frames

        # TODO: update progress bar

    def clear_session(self) -> None:
        self.app_state = AppState()
        logger.info("Session cleared")

    def finish_and_close(self):
        if self.video_viewer:
            self.video_viewer.stop()

        if self.app_state.auto_save:
            # TODO: Figure out save path
            # self.save_session()
            return

        # if save_session_answer:
        #     self.save_session()


SKELLYCLICKER_APP: SkellyclickerApp | None = None

def create_skellyclicker_app(app_state: AppState | None = None) -> SkellyclickerApp:
    """
    Create and return the SkellyClicker application instance.
    """
    global SKELLYCLICKER_APP
    if not SKELLYCLICKER_APP:
        SKELLYCLICKER_APP = SkellyclickerApp.create(app_state=app_state)
    else:
        raise Exception("SkellyClicker app already created, but you tried to create it again!")
    return SKELLYCLICKER_APP

def get_skellyclicker_app() -> SkellyclickerApp:
    global SKELLYCLICKER_APP
    if not SKELLYCLICKER_APP:
        raise Exception("SkellyClicker app not created yet!")
    return SKELLYCLICKER_APP