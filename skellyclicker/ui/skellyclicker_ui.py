import tkinter as tk
from dataclasses import dataclass

from skellyclicker.ui.mvc.ui_controller import SkellyClickerUIController
from skellyclicker.ui.mvc.ui_model import SkellyClickerUIModel
from skellyclicker.ui.mvc.ui_view import SkellyClickerUIView


@dataclass
class SkellyClickerUi:
    root: tk.Tk
    ui_model: SkellyClickerUIModel
    ui_view: SkellyClickerUIView
    ui_controller: SkellyClickerUIController

    @classmethod
    def create_ui(cls):
        root = tk.Tk()
        root.title("SkellyClicker UI")
        root.minsize(300, 400)

        ui_model: SkellyClickerUIModel = SkellyClickerUIModel()
        ui_view: SkellyClickerUIView = SkellyClickerUIView.create_ui(root=root)
        ui_controller: SkellyClickerUIController = SkellyClickerUIController(ui_model=ui_model,
                                                                             ui_view=ui_view)
        cls._bind_controller(ui_controller=ui_controller,
                             ui_view=ui_view)
        return cls(root=root,
                   ui_model=ui_model,
                   ui_view=ui_view,
                   ui_controller=ui_controller,
                   )


    @classmethod
    def _bind_controller(cls, ui_view: SkellyClickerUIView, ui_controller: SkellyClickerUIController) -> None:
        ui_view.load_videos_button.config(command=ui_controller.load_videos)

        ui_view.load_deeplabcut_button.config(command=ui_controller.load_deeplabcut_project)
        ui_view.create_deeplabcut_button.config(command=ui_controller.create_deeplabcut_project)
        ui_view.train_deeplabcut_model_button.config(command=ui_controller.train_model)

        ui_view.play_button.config(command=ui_controller.play_video)
        ui_view.pause_button.config(command=ui_controller.pause_video)

        ui_view.autosave_checkbox.config(command=ui_controller.on_autosave_toggle)
        ui_view.save_csv_button.config(command=ui_controller.save_file)
        ui_view.clear_session_button.config(command=ui_controller.clear_session)

        ui_view.show_help_checkbox.config(command=ui_controller.on_show_help_toggle)


if __name__ == "__main__":
    _ui = SkellyClickerUi.create_ui()
    _ui.root.mainloop()
