import tkinter as tk
from dataclasses import dataclass

from skellyclicker.tk_ui.mvc.ui_controller import SkellyClickerUIController
from skellyclicker.tk_ui.mvc.ui_model import SkellyClickerUIModel
from skellyclicker.tk_ui.mvc.ui_view import SkellyClickerUIView


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
        
        instance = cls(
            root=root,
            ui_model=ui_model,
            ui_view=ui_view,
            ui_controller=ui_controller
        )

        instance.root.protocol("WM_DELETE_WINDOW", instance.on_closing)

        return instance


    @classmethod
    def _bind_controller(cls, ui_view: SkellyClickerUIView, ui_controller: SkellyClickerUIController) -> None:
        ui_view.load_videos_button.config(command=ui_controller.load_videos)
        ui_view.open_videos_button.config(command=ui_controller.open_videos)

        ui_view.load_deeplabcut_button.config(command=ui_controller.load_deeplabcut_project)
        ui_view.create_deeplabcut_button.config(command=ui_controller.create_deeplabcut_project)
        ui_view.train_deeplabcut_model_button.config(command=ui_controller.train_model)
        ui_view.analyze_videos_button.config(command=ui_controller.analyze_videos)
        ui_view.annotate_videos_checkbox.config(command=ui_controller.on_annotate_videos_toggle)
        ui_view.deeplabcut_filter_predictions_checkbox.config(command=ui_controller.on_filter_predictions_toggle)
        ui_view.deeplabcut_epochs_spinbox.config(command=ui_controller.on_training_epochs_change)
        ui_view.deeplabcut_save_epochs_spinbox.config(command=ui_controller.on_training_save_epochs_change)
        ui_view.deeplabcut_batch_size_spinbox.config(command=ui_controller.on_training_batch_size_change)

        # ui_view.play_button.config(command=ui_controller.play_video)
        # ui_view.pause_button.config(command=ui_controller.pause_video)

        ui_view.autosave_checkbox.config(command=ui_controller.on_autosave_toggle)
        ui_view.save_session_button.config(command=ui_controller.save_session)
        ui_view.load_session_button.config(command=ui_controller.load_session)
        ui_view.clear_session_button.config(command=ui_controller.clear_session)
        ui_view.load_click_data_button.config(command=ui_controller.load_labels_csv)
        ui_view.load_machine_labels_button.config(command=ui_controller.load_machine_labels_csv)
        ui_view.clear_click_data_button.config(command=ui_controller.clear_labels_csv)
        ui_view.clear_machine_labels_button.config(command=ui_controller.clear_machine_labels_csv)
        #
        # ui_view.show_help_checkbox.config(command=ui_controller.on_show_help_toggle)

    def on_closing(self):
        self.ui_controller.finish_and_close()
        self.root.destroy()

if __name__ == "__main__":
    _ui = SkellyClickerUi.create_ui()
    _ui.root.mainloop()
