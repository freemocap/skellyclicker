import time
import os
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, simpledialog, messagebox, NORMAL, DISABLED

from pydantic import ValidationError

from skellyclicker.ui.mvc.ui_model import SkellyClickerUIModel
from skellyclicker.core.deeplabcut_handler.deeplabcut_handler import DeeplabcutHandler
from skellyclicker.ui.mvc.ui_view import SkellyClickerUIView
from skellyclicker.core.video_handler.video_viewer import VideoViewer

DEEPLABCUT_CONFIG_FILE_NAME = "config.yaml"


@dataclass
class SkellyClickerUIController:
    ui_view: SkellyClickerUIView
    ui_model: SkellyClickerUIModel

    video_viewer: VideoViewer | None = None
    deeplabcut_handler: DeeplabcutHandler | None = None

    def load_deeplabcut_project(self) -> None:
        project_path = filedialog.askdirectory(
            title="Select DeepLabCut Project Directory"
        )
        if project_path:
            self.ui_model.project_path = project_path
            self.ui_view.deeplabcut_project_path_var.set(project_path)
            self.deeplabcut_handler = DeeplabcutHandler.load_deeplabcut_project(project_config_path=str(Path(project_path) / DEEPLABCUT_CONFIG_FILE_NAME))
            print(f"DeepLabCut project loaded from: {project_path}")

    def create_deeplabcut_project(self) -> None:
        project_path = filedialog.askdirectory(
            title="Select Directory for New DeepLabCut Project"
        )
        if project_path:
            project_name = simpledialog.askstring(
                "DeepLabCut Project Name", "Enter name for new deeplabcut project:"
            )
            if project_name:
                full_project_path = os.path.join(project_path, project_name)
                self.ui_model.project_path = full_project_path
                self.ui_view.deeplabcut_project_path_var.set(full_project_path)
                
                if self.video_viewer:
                    tracked_point_names = self.video_viewer.video_handler.data_handler.config.tracked_point_names
                else:
                    print("No tracked point names available, load and label videos before creating deeplabcut project")
                    return
                self.deeplabcut_handler = DeeplabcutHandler.create_deeplabcut_project(
                    project_name=project_name,
                    project_parent_directory=project_path,
                    tracked_point_names=tracked_point_names,
                    connections=None, # TODO: Handle connections somehow
                )
                    
                print(f"Creating new deeplabcut project: {full_project_path}")

    def load_videos(self) -> None:
        video_files = filedialog.askopenfilenames(
            title="Select Videos",
            filetypes=[("Video files", "*.mp4 *.avi *.mov"), ("All files", "*.*")],
        )
        if video_files:
            self.ui_model.video_files = list(video_files)
            self.ui_view.open_videos_button.config(state=NORMAL)
            self.open_videos()

    def open_videos(self) -> None:
        if self.ui_model.video_files:
            self.ui_model.video_files = list(self.ui_model.video_files)
            self.ui_view.videos_directory_path_var.set(
                ", ".join(self.ui_model.video_files)
            )
            print(f"Videos loaded: {len(self.ui_model.video_files)} files")
            if self.video_viewer:
                self.video_viewer.stop()  # TODO: no close method implemented
                while self.video_viewer:
                    time.sleep(0.1)

            if self.ui_model.csv_saved_path:
                self.video_viewer = VideoViewer.from_videos(
                    video_paths=self.ui_model.video_files,
                    data_handler_path=self.ui_model.csv_saved_path,
                    machine_labels_path=self.ui_model.machine_labels_path,
                )
            else:
                self.video_viewer = VideoViewer.from_videos(
                    video_paths=self.ui_model.video_files,
                    machine_labels_path=self.ui_model.machine_labels_path,
                )
            self.video_viewer.on_complete = self.video_viewer_on_complete
            self.video_viewer.launch_video_thread()

    def video_viewer_on_complete(self) -> None:
        if self.video_viewer is None:
            print("Video viewer closed while not initialized")
            return
        save_data = messagebox.askyesno("Save Data", "Would you like to save the data?")
        if save_data is False:
            save_data = messagebox.askyesno(
                "Save Data Confirmation",
                "Confirm your choice: Click 'yes' to prevent data loss or 'no' to delete this session forever:",
            )
        save_path = self.video_viewer.video_handler.close(save_data=save_data)

        if save_data and save_path:
            self.ui_model.csv_saved_path = save_path
            self.ui_view.click_save_path_var.set(save_path)
            messagebox.showinfo("Data Saved", f"Data saved to: {save_path}")
        else:
            messagebox.showinfo("Data Not Saved", "Data not saved.")

        self.video_viewer = None

    def train_model(self) -> None:
        if not self.ui_model.project_path:
            messagebox.showinfo("No Project", "Please load or create a project first")
            return
        print("Training model...")
        if self.deeplabcut_handler is None:
            messagebox.showinfo(
                "No DeepLabCut Handler", "DeepLabCut handler not initialized"
            )
            return 
        if not self.ui_model.video_files:
            messagebox.showinfo("No Videos", "Attempted to train model without loading videos, must load videos and label before training")
            return
        if not self.ui_model.csv_saved_path:
            messagebox.showinfo("No Data", "Attempted to train model without saving data, must label videos before training")
            return
        # TODO: make training config gui options
        self.deeplabcut_handler.train_model(labels_csv_path=self.ui_model.csv_saved_path, video_paths=self.ui_model.video_files)

        print("Model completed training")

    def analyze_videos(self) -> None:
        if not self.ui_model.project_path:
            messagebox.showinfo("No Project", "Please load or create a project first")
            return
        print("Analyzing videos...")
        if self.deeplabcut_handler is None:
            messagebox.showinfo(
                "No DeepLabCut Handler", "DeepLabCut handler not initialized"
            )
            return 
        
        analyze_training_videos_dialog = messagebox.askyesnocancel(
            "Analyze training videos",
            "Would you like to analyze the training videos?",
        )

        if analyze_training_videos_dialog is None:
            return
        elif analyze_training_videos_dialog is True:
            video_paths = self.ui_model.video_files
            copy_to_machine_labels = True
        else:
            copy_to_machine_labels = False
            video_paths = filedialog.askopenfilenames(
                title="Select Videos",
                filetypes=[("Video files", "*.mp4 *.avi *.mov"), ("All files", "*.*")],
            )

        if video_paths is None or len(video_paths) == 0:
            messagebox.showinfo("No Videos", "No videos selected for analysis")
            return

        machine_labels_path = self.deeplabcut_handler.analyze_videos(video_paths=video_paths, annotate_videos=self.ui_model.annotate_videos)

        if copy_to_machine_labels:
            self.ui_model.machine_labels_path = machine_labels_path
        print("Videos analyzed")

    def set_save_path(self) -> None:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if file_path:
            self.ui_model.csv_saved_path = file_path
            self.ui_view.click_save_path_var.set(file_path)
            print(f"New save path set to: {file_path}")

    def save_session(self) -> None:
        output_directory = (
            Path(self.ui_model.session_saved_path).parent
            if self.ui_model.session_saved_path
            else None
        )
        output_filename = (
            Path(self.ui_model.session_saved_path).name
            if self.ui_model.session_saved_path
            else None
        )

        output_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=output_directory,
            initialfile=output_filename,
        )
        json_data = self.ui_model.model_dump_json()

        with open(output_path, "w") as f:
            f.write(json_data)

        print(f"Session successfully saved to: {output_path}")

    def load_session(self) -> None:
        json_file = filedialog.askopenfilename(
            title="Select Session File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        with open(json_file, "r") as f:
            json_data = f.read()

        try:
            self.ui_model = SkellyClickerUIModel.model_validate_json(json_data)
            self.ui_model.session_saved_path = json_file
        except ValidationError as e:
            print(f"Error loading session: {e}")
            return
        
        if self.deeplabcut_handler:
            print("WARNING: Project loaded while deeplabcut handler already initialized, closing deeplabcut project")
        if self.ui_model.project_path:
            self.ui_view.deeplabcut_project_path_var.set(self.ui_model.project_path)
            self.deeplabcut_handler = DeeplabcutHandler.load_deeplabcut_project(project_config_path=str(Path(self.ui_model.project_path) / DEEPLABCUT_CONFIG_FILE_NAME))
        else:
            self.deeplabcut_handler = None

        self.sync_ui_with_model()

        print(f"Session successfully loaded from: {json_file}")

    def sync_ui_with_model(self) -> None:
        self.ui_view.autosave_boolean_var.set(self.ui_model.auto_save)
        self.ui_view.show_help_boolean_var.set(self.ui_model.show_help)
        self.ui_view.annotate_videos_boolean_var.set(self.ui_model.annotate_videos)
        if self.ui_model.video_files:
            self.ui_view.videos_directory_path_var.set(
                ", ".join(self.ui_model.video_files)
            )
            self.ui_view.open_videos_button.config(state=NORMAL)
        else:
            self.ui_view.open_videos_button.config(state=DISABLED)
        if self.ui_model.csv_saved_path:
            self.ui_view.click_save_path_var.set(self.ui_model.csv_saved_path)
        if self.ui_model.project_path:
            self.ui_view.deeplabcut_project_path_var.set(self.ui_model.project_path)

    def on_autosave_toggle(self) -> None:
        self.ui_model.auto_save = self.ui_view.autosave_boolean_var.get()
        print(f"Auto-save set to: {self.ui_model.auto_save}")

    def on_show_help_toggle(self) -> None:
        self.ui_model.show_help = self.ui_view.show_help_boolean_var.get()
        print(f"Show help set to: {self.ui_model.show_help}")

    def on_annotate_videos_toggle(self) -> None:
        self.ui_model.annotate_videos = self.ui_view.annotate_videos_boolean_var.get()
        print(f"Annotate videos set to: {self.ui_model.annotate_videos}")

    def clear_session(self) -> None:
        response = messagebox.askyesno(
            "Confirmation", "Are you sure you want to clear the session?"
        )
        if response:
            self.ui_model = SkellyClickerUIModel()
            self.sync_ui_with_model()
            print("Session cleared")

    def finish_and_close(self):
        if self.video_viewer:
            self.video_viewer.stop()

        if self.ui_model.auto_save:
            self.save_session()
            return

        save_session_answer = messagebox.askyesno(
            "Save Session", "Would you like to save this session?"
        )
        if save_session_answer is False:
            save_session_answer = messagebox.askyesno(
                "Save Session Confirmation",
                "Confirm your choice: Click 'yes' to prevent data loss or 'no' to delete this session forever:",
            )

        if save_session_answer:
            self.save_session()
