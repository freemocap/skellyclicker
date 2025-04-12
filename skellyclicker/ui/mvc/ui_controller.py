import os
from dataclasses import dataclass
from tkinter import filedialog, simpledialog, messagebox

from skellyclicker.ui.mvc.ui_model import SkellyClickerUIModel
from skellyclicker.core.deeplabcut_handler.deeplabcut_handler import DeeplabcutHandler
from skellyclicker.ui.mvc.ui_view import SkellyClickerUIView
from skellyclicker.core.video_handler.video_viewer import VideoViewer


@dataclass
class SkellyClickerUIController:
    ui_view: SkellyClickerUIView
    ui_model: SkellyClickerUIModel

    video_viewer: VideoViewer | None = None
    deeplabcut_handler: DeeplabcutHandler | None = None
    # click_data_handler: None

    def load_deeplabcut_project(self) -> None:
        project_path = filedialog.askdirectory(title="Select DeepLabCut Project Directory")
        if project_path:
            self.ui_model.project_path = project_path
            self.ui_view.deeplabcut_project_path_var.set(project_path)
            self.deeplabcut_handler.load_project(project_path=project_path)
            print(f"DeepLabCut project loaded from: {project_path}")

    def create_deeplabcut_project(self) -> None:
        project_path = filedialog.askdirectory(title="Select Directory for New DeepLabCut Project")
        if project_path:
            project_name = simpledialog.askstring("DeepLabCut Project Name", "Enter name for new deeplabcut project:")
            if project_name:
                full_project_path = os.path.join(project_path, project_name)
                self.ui_model.project_path = full_project_path
                self.ui_view.deeplabcut_project_path_var.set(full_project_path)
                # self.deeplabcut_handler.create_deeplabcut_project(deeplabcut_project_path=full_project_path)
                print(f"Creating new deeplabcut project: {full_project_path}")

    def load_videos(self) -> None:
        video_files = filedialog.askopenfilenames(
            title="Select Videos",
            filetypes=[("Video files", "*.mp4 *.avi *.mov"), ("All files", "*.*")]
        )
        if video_files:
            self.ui_model.video_files = list(video_files)
            self.ui_view.videos_directory_path_var.set(", ".join(video_files))
            print(f"Videos loaded: {len(video_files)} files")
            if self.video_viewer:
                self.video_viewer.close()  # TODO: no close method implemented
            self.video_viewer = VideoViewer.from_videos(self.ui_model.video_files)
            self.video_viewer.on_complete = self.video_viewer_on_complete
            self.video_viewer.launch_video_thread()
            # TODO: have save dialog show up as gui popup

    def video_viewer_on_complete(self) -> None:
        if self.video_viewer is None:
            print("Video viewer closed while not initialized")
            return
        save_data = messagebox.askyesno("Save Data", "Would you like to save the data?")
        if save_data is False:
            save_data = messagebox.askyesno("Save Data Confirmation", "Confirm your choice: Click 'yes' to prevent data loss or 'no' to delete this session forever:")
        save_path = self.video_viewer.video_handler.close(save_data=save_data)

        if save_data:
            self.ui_model.csv_saved_path = save_path
            messagebox.showinfo("Data Saved", f"Data saved to: {save_path}")
        else:
            messagebox.showinfo("Data Not Saved", "Data not saved.")

    def train_model(self) -> None:
        if not self.ui_model.project_path:
            messagebox.showinfo("No Project", "Please load or create a project first")
            return
        print("Training model...")
        if self.deeplabcut_handler is None:
            messagebox.showinfo("No DeepLabCut Handler", "DeepLabCut handler not initialized")
            return
        self.deeplabcut_handler.train_model(project_path=self.ui_model.project_path)


    def save_file(self) -> None:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            self.ui_model.csv_saved_path = file_path
            self.ui_view.click_save_path_var.set(file_path)
            print(f"File saved to: {file_path}")

    def on_autosave_toggle(self) -> None:
        self.ui_model.auto_save = self.ui_view.autosave_boolean_var.get()
        print(f"Auto-save set to: {self.ui_model.auto_save}")

    def on_show_help_toggle(self) -> None:
        self.ui_model.show_help = self.ui_view.show_help_boolean_var.get()
        print(f"Show help set to: {self.ui_model.show_help}")

    def clear_session(self) -> None:
        response = messagebox.askyesno("Confirmation", "Are you sure you want to clear the session?")
        if response:
            self.ui_model = SkellyClickerUIModel()
            print("Session cleared")

    def finish_and_close(self):
        if self.video_viewer:
            self.video_viewer.stop()
