import os
from dataclasses import field, dataclass
from tkinter import filedialog, simpledialog, messagebox

from skellyclicker.ui_view.ui_mvc.ui_state import SkellyClickerUIState
from skellyclicker.ui_view.ui_mvc.ui_view import SkellyClickerUIView


@dataclass
class SkellyClickerUIController:
    view: SkellyClickerUIView
    ui_state: SkellyClickerUIState = field(default_factory=SkellyClickerUIState)

    def load_deeplabcut_project(self) -> None:
        project_path = filedialog.askdirectory(title="Select DeepLabCut Project Directory")
        if project_path:
            self.ui_state.project_path=project_path
            self.view.deeplabcut_project_path_var.set(project_path)
            print(f"DeepLabCut project loaded from: {project_path}")

    def create_deeplabcut_project(self) -> None:
        project_path = filedialog.askdirectory(title="Select Directory for New DeepLabCut Project")
        if project_path:
            project_name = simpledialog.askstring("DeepLabCut Project Name", "Enter name for new deeplabcut project:")
            if project_name:
                full_project_path = os.path.join(project_path, project_name)
                self.ui_state.project_path = full_project_path
                self.view.deeplabcut_project_path_var.set(full_project_path)
                print(f"Creating new deeplabcut project: {full_project_path}")

    def load_videos(self) -> None:
        video_files = filedialog.askopenfilenames(
            title="Select Videos",
            filetypes=[("Video files", "*.mp4 *.avi *.mov"), ("All files", "*.*")]
        )
        if video_files:
            self.ui_state.video_files = list(video_files)
            self.view.videos_directory_path_var.set(", ".join(video_files))
            print(f"Videos loaded: {len(video_files)} files")

    def play_video(self) -> None:
        if not self.ui_state.video_files:
            messagebox.showinfo("No Videos", "Please load videos first")
            return
        self.ui_state.is_playing = True
        print("Playing video")

    def pause_video(self) -> None:
        self.ui_state.is_playing = False
        print("Video paused")

    def train_model(self) -> None:
        if not self.ui_state.project_path:
            messagebox.showinfo("No Project", "Please load or create a project first")
            return
        print("Training model...")

    def save_file(self) -> None:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if file_path:
            self.ui_state.saved_path = file_path
            print(f"File saved to: {file_path}")

    def on_auto_toggle(self) -> None:
        self.ui_state.auto_save = self.view.autosave_boolean_var.get()
        print(f"Auto-save set to: {self.ui_state.auto_save}")

    def on_help_toggle(self) -> None:
        self.ui_state.show_help = self.view.show_help_boolean_var.get()
        print(f"Show help set to: {self.ui_state.show_help}")

    def clear_session(self) -> None:
        response = messagebox.askyesno("Confirmation", "Are you sure you want to clear the session?")
        if response:
            self.ui_state = SkellyClickerUIState()
            print("Session cleared")

