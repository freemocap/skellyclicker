import tkinter as tk
from dataclasses import dataclass

from skellyclicker.ui_view.ui_mvc.ui_controller import SkellyClickerUIController
from skellyclicker.ui_view.ui_mvc.ui_state import SkellyClickerUIState
from skellyclicker.ui_view.ui_mvc.ui_view import SkellyClickerUIView


@dataclass
class SkellyClickerUI:
    root: tk.Tk
    ui_state: SkellyClickerUIState
    controller: SkellyClickerUIController
    view: SkellyClickerUIView
    @classmethod
    def create_ui(cls):
        root = tk.Tk()
        root.title("SkellyClicker UI")
        root.minsize(300, 300)
        ui_state: SkellyClickerUIState = SkellyClickerUIState()
        view = cls._create_widgets(root)
        controller: SkellyClickerUIController = SkellyClickerUIController(view=view, ui_state=ui_state)
        cls._bind_controller(view, controller)
        return cls(root=root, ui_state=ui_state, controller=controller, view=view)

    @classmethod
    def _create_widgets(cls, root: tk.Tk):
        view = SkellyClickerUIView()
        view.main_frame = tk.Frame(root, padx=20, pady=20)
        view.main_frame.pack(fill=tk.BOTH, expand=True)

        cls._create_deeplabcut_frame(view)
        cls._create_videos_frame(view)
        cls._create_playback_section(view)

        separator = tk.Frame(view.main_frame, height=2, bg="gray")
        separator.pack(fill=tk.X, pady=10)

        cls._create_save_option_frame(view)
        cls._create_show_help_frame(view)
        cls._create_clear_session_frame(view)

        return view
    @classmethod
    def _bind_controller(cls, view: SkellyClickerUIView, controller: SkellyClickerUIController) -> None:
        view.load_deeplabcut_button.config(command=controller.load_deeplabcut_project)
        view.create_deeplabcut_button.config(command=controller.create_deeplabcut_project)
        view.load_videos_button.config(command=controller.load_videos)
        view.play_button.config(command=controller.play_video)
        view.pause_button.config(command=controller.pause_video)
        view.train_deeplabcut_model_button.config(command=controller.train_model)
        view.save_csv_button.config(command=controller.save_file)
        view.autosave_checkbox.config(command=controller.on_auto_toggle)
        view.show_help_checkbox.config(command=controller.on_help_toggle)
        view.clear_session_button.config(command=controller.clear_session)

    @classmethod
    def _create_deeplabcut_frame(cls, view: SkellyClickerUIView):
        view.deeplabcut_frame = tk.Frame(view.main_frame)
        view.deeplabcut_frame.pack(fill=tk.X, pady=5)

        view.load_deeplabcut_button = tk.Button(view.deeplabcut_frame, text="Load")
        view.load_deeplabcut_button.pack(side=tk.LEFT, padx=5)

        view.create_deeplabcut_button = tk.Button(view.deeplabcut_frame, text="Create")
        view.create_deeplabcut_button.pack(side=tk.LEFT, padx=5)

        view.deeplabcut_project_label = tk.Label(view.deeplabcut_frame, text="Deeplabcut Project")
        view.deeplabcut_project_label.pack(side=tk.LEFT, padx=5)
        view.deeplabcut_project_label.pack(fill=tk.X)

        view.train_deeplabcut_model_button = tk.Button(view.deeplabcut_frame, text="Train DLC Model")

    @classmethod
    def _create_videos_frame(cls, view: SkellyClickerUIView):
        view.load_videos_frame = tk.Frame(view.main_frame)
        view.load_videos_frame.pack(fill=tk.X, pady=5)

        view.load_videos_button = tk.Button(view.load_videos_frame, text="Load Videos")
        view.load_videos_button.pack(side=tk.LEFT, padx=5)

        view.videos_directory_label = tk.Label(view.load_videos_frame, textvariable=view.videos_directory_path_var)
        view.videos_directory_label.pack(side=tk.LEFT, padx=5)


    @classmethod
    def _create_playback_section(cls, view: SkellyClickerUIView):
        view.playback_frame = tk.Frame(view.main_frame)
        view.playback_frame.pack(fill=tk.X, pady=5)

        view.play_button = tk.Button(view.playback_frame, text="Play")
        view.play_button.pack(side=tk.LEFT, padx=5)

        view.pause_button = tk.Button(view.playback_frame, text="Pause")
        view.pause_button.pack(side=tk.LEFT, padx=5)

        view.step_size_spinbox = tk.Spinbox(view.playback_frame, from_=1, to=1000)
        view.step_size_spinbox.pack(side=tk.LEFT, padx=5)

        view.frame_number_slider = tk.Scale(view.playback_frame, from_=0, to=1000)
        view.frame_number_slider.pack(side=tk.LEFT, padx=5)


    @classmethod
    def _create_save_option_frame(cls, view: SkellyClickerUIView):
        """Create the options section with auto-save and save button."""
        view.save_options_frame = tk.Frame(view.main_frame)
        view.save_options_frame.pack(fill=tk.X, pady=5)

        view.autosave_checkbox = tk.Checkbutton(
            view.save_options_frame,
            text="Auto",
            variable=view.autosave_boolean_var,
        )
        view.autosave_checkbox.pack(side=tk.LEFT)

        view.save_csv_button = tk.Button(
            view.save_options_frame,
            text="Save Labels to CSV",
        )
        view.save_csv_button.pack(side=tk.LEFT, padx=10)

        view.click_save_path_label = tk.Label(
            view.save_options_frame,
            textvariable=view.click_save_path_var,
        )
        view.click_save_path_label.pack(side=tk.LEFT, padx=5)

        view.clear_session_button = tk.Button(
            view.save_options_frame,
            text="Clear Session",
        )

    @classmethod
    def _create_show_help_frame(cls, view: SkellyClickerUIView):
        """Create the help section."""
        view.show_help_frame = tk.Frame(view.main_frame)
        view.show_help_frame.pack(fill=tk.X, pady=5)

        view.show_help_checkbox = tk.Checkbutton(
            view.show_help_frame,
            text="Show Help",
            variable=view.show_help_boolean_var,
        )
        view.show_help_checkbox.pack(fill=tk.X)

    @classmethod
    def _create_clear_session_frame(cls, view: SkellyClickerUIView):
        """Create the session clearing section."""
        view.clear_frame = tk.Frame(view.main_frame)
        view.clear_frame.pack(fill=tk.X, pady=5)

        view.clear_btn = tk.Button(
            view.clear_frame,
            text="Clear Session",
        )
        view.clear_btn.pack(fill=tk.X)

if __name__ == "__main__":
    _app = SkellyClickerUI.create_ui()
    _app.root.mainloop()
