# skellyclicker/ui/mvc/ui_view.py
import logging
import platform
import tkinter as tk
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageTk

import skellyclicker
from skellyclicker.ui.assets.logo_paths import SKELLYCLICKER_LOGO_PNG, SKELLYCLICKER_LOGO_ICO
from skellyclicker.ui.tk_components.labeling_progress import LabelingProgress

logger = logging.getLogger(__name__)

@dataclass
class SkellyClickerUIView:
    root: tk.Tk
    main_frame: tk.Frame = None

    # Header frame
    header_frame: tk.Frame = None
    logo_image_tk: ImageTk = None

    # Load videos section
    videos_directory_path_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="No videos loaded"))
    load_videos_frame: tk.Frame = None
    load_videos_button: tk.Button = None
    open_videos_button: tk.Button = None
    videos_directory_label: tk.Label = None

    # Playback section
    playback_frame: tk.Frame = None
    current_frame_number_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="0"))
    start_frame_number_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="0"))
    end_frame_number_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="-1"))
    play_button: tk.Button = None
    pause_button: tk.Button = None
    step_size_spinbox: tk.Spinbox = None
    frame_number_slider: tk.Scale = field(
        default_factory=lambda: tk.Scale(
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            label="Frame Number",
            length=200,
            resolution=1,
            tickinterval=50,
            showvalue=True
        )
    )
    frames_per_second_var: tk.Scale = field(default_factory=lambda: tk.Scale(
        from_=1,
        to=300,
        orient=tk.HORIZONTAL,
        label="FPS",
        length=200,
        resolution=1,
        tickinterval=50,
        showvalue=True
    ))

    # Deeplabcut section
    deeplabcut_project_path_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="No project loaded"))
    deeplabcut_frame: tk.Frame = None
    create_deeplabcut_button: tk.Button = None
    load_deeplabcut_button: tk.Button = None
    deeplabcut_project_label: tk.Label = None
    train_deeplabcut_model_button: tk.Button = None
    analyze_videos_button: tk.Button = None
    annotate_videos_boolean_var: tk.BooleanVar = field(default_factory=tk.BooleanVar)
    annotate_videos_checkbox: tk.Checkbutton = None
    deeplabcut_filter_predictions_var: tk.BooleanVar = field(default_factory=tk.BooleanVar)
    deeplabcut_filter_predictions_checkbox: tk.Checkbutton = None

    deeplabcut_options_frame: tk.Frame = None
    current_iteration_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="None"))
    current_iteration_header_label: tk.Label = None
    current_iteration_label: tk.Label = None

    deeplabcut_training_frame: tk.Frame = None
    deeplabcut_epochs_label: tk.Label = None
    deeplabcut_epochs_spinbox: tk.Spinbox = None
    deeplabcut_epochs_var: tk.IntVar = field(default_factory=lambda: tk.IntVar(value=200))
    deeplabcut_save_epochs_label: tk.Label = None
    deeplabcut_save_epochs_spinbox: tk.Spinbox = None
    deeplabcut_save_epochs_var: tk.IntVar = field(default_factory=lambda: tk.IntVar(value=20))
    deeplabcut_batch_size_label: tk.Label = None
    deeplabcut_batch_size_spinbox: tk.Spinbox = None
    deeplabcut_batch_size_var: tk.IntVar = field(default_factory=lambda: tk.IntVar(value=1))

    # Save section
    save_options_frame: tk.Frame = None
    autosave_checkbox: tk.Checkbutton = None
    autosave_boolean_var: tk.BooleanVar = field(default_factory=tk.BooleanVar)
    click_save_path_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="No file saved"))
    click_save_path_label: tk.Label = None
    load_click_data_button: tk.Button = None
    clear_click_data_button: tk.Button = None
    machine_labels_path_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="No file saved"))
    machine_labels_path_label: tk.Label = None
    load_machine_labels_button: tk.Button = None
    clear_machine_labels_button: tk.Button = None
    save_session_button: tk.Button = None
    load_session_button: tk.Button = None
    clear_session_button: tk.Button = None

    # Info section
    show_help_frame: tk.Frame = None
    show_help_boolean_var: tk.BooleanVar = field(default_factory=tk.BooleanVar)
    show_help_checkbox: tk.Checkbutton = None

    # Progress section
    progress_frame: tk.Frame = None
    progress_label: tk.Label = None
    total_rows_var: tk.IntVar = field(default_factory=lambda: tk.IntVar(value=0))
    labeling_progress: LabelingProgress = None


    @classmethod
    def create_ui(cls, root: tk.Tk):
        """Create the main UI frame."""
        instance = cls(root=root)
        instance.main_frame = tk.Frame(root)
        instance.main_frame.pack(fill=tk.BOTH, expand=True)


        # Set up the app icon
        instance.set_app_icon()

        # Create components inside the sidebar
        instance._create_header()
        instance._create_separator()
        instance._create_separator()

        instance._create_save_option_frame()
        instance._create_separator()

        instance._create_videos_frame()
        instance._create_separator()

        instance._create_deeplabcut_frame()
        instance._create_deeplabcut_options_frame()
        instance._create_deeplabcut_training_frame()
        instance._create_separator()

        # instance._create_playback_section()
        # instance._create_separator()
        instance._create_progress_frame()
        instance._create_separator()
        #
        # instance._create_show_help_frame()


        return instance



    def _create_header(self):
        """Create the header with logo."""
        self.header_frame = tk.Frame(self.main_frame)
        self.header_frame.pack(fill=tk.X, pady=5)

        self._add_logo()

        # Create a frame to stack text vertically
        text_frame = tk.Frame(self.header_frame)
        text_frame.pack(side=tk.LEFT, padx=10)

        # Create a title label above the image
        title_text = "SkellyClicker"
        subtitle_text = "for clicking on stuff"
        link_text = skellyclicker.__url__
        title_label = tk.Label(text_frame, text=title_text, font=("Arial", 14, "bold"))
        subtitle_label = tk.Label(text_frame, text=subtitle_text, font=("Arial", 10))
        link_label = tk.Label(text_frame, text=link_text, font=("Arial", 8, "underline"), fg="blue", cursor="hand2")

        title_label.pack(anchor='w')
        subtitle_label.pack(anchor='w')
        link_label.pack(anchor='w')

        # Bind click event to open the GitHub repository
        link_label.bind("<Button-1>", lambda e: webbrowser.open(skellyclicker.__url__))

    def _add_logo(self):
        try:
            # Load the logo image using PIL (you may need to install pillow: pip install pillow)
            logo_img = Image.open(SKELLYCLICKER_LOGO_PNG)
            # Resize the image to be smaller (adjust size as needed)
            logo_img = logo_img.resize((100, 100), Image.Resampling.LANCZOS)
            # Convert to PhotoImage that tkinter can display
            self.logo_image_tk = ImageTk.PhotoImage(logo_img)

            # Create a label to display the image
            logo_label = tk.Label(self.header_frame, image=self.logo_image_tk, cursor="hand2")
            logo_label.pack(side=tk.LEFT, padx=10)

            # Bind click event to open the GitHub repository
            logo_label.bind("<Button-1>", lambda e: webbrowser.open(skellyclicker.__url__))
        except Exception as e:
            logger.error(f"Error loading logo: {e} - continuing without it) ")

    def _create_separator(self):
        """Create a separator line."""
        separator = tk.Frame(self.main_frame, height=2, bd=1, relief=tk.SUNKEN)
        separator.pack(fill=tk.X, padx=5, pady=5)
        return separator

    def _create_deeplabcut_frame(self):
        self.deeplabcut_frame = tk.Frame(self.main_frame)
        self.deeplabcut_frame.pack(fill=tk.X, pady=5)

        self.create_deeplabcut_button = tk.Button(self.deeplabcut_frame, text="Create")
        self.create_deeplabcut_button.pack(side=tk.LEFT, padx=5)

        self.load_deeplabcut_button = tk.Button(self.deeplabcut_frame, text="Load")
        self.load_deeplabcut_button.pack(side=tk.LEFT, padx=5)

        self.deeplabcut_project_label = tk.Label(self.deeplabcut_frame, text="Deeplabcut Project")
        self.deeplabcut_project_label.pack(side=tk.LEFT, padx=5)
        self.deeplabcut_project_label.pack(fill=tk.X)

        self.train_deeplabcut_model_button = tk.Button(self.deeplabcut_frame, text="Train DLC Model")
        self.train_deeplabcut_model_button.pack(side=tk.LEFT, padx=5)

    def _create_deeplabcut_options_frame(self):
        self.deeplabcut_options_frame = tk.Frame(self.main_frame)
        self.deeplabcut_options_frame.pack(fill=tk.X, pady=5)

        self.analyze_videos_button = tk.Button(self.deeplabcut_options_frame, text="Analyze Videos")
        self.analyze_videos_button.pack(side=tk.LEFT, padx=5)

        self.annotate_videos_checkbox = tk.Checkbutton(self.deeplabcut_options_frame, text="Annotate Videos", variable=self.annotate_videos_boolean_var)
        self.annotate_videos_checkbox.pack(side=tk.LEFT, padx=5)

        self.deeplabcut_filter_predictions_checkbox = tk.Checkbutton(self.deeplabcut_options_frame, text="Filter Predictions", variable=self.deeplabcut_filter_predictions_var)
        self.deeplabcut_filter_predictions_checkbox.pack(side=tk.LEFT, padx=5)

        self.current_iteration_header_label = tk.Label(self.deeplabcut_options_frame, text="Current Iteration:")
        self.current_iteration_header_label.pack(side=tk.LEFT, padx=5)
        self.current_iteration_header_label.pack(fill=tk.X)

        self.current_iteration_label = tk.Label(self.deeplabcut_options_frame, textvariable=self.current_iteration_var)
        self.current_iteration_label.pack(side=tk.LEFT, padx=5)
        self.current_iteration_label.pack(fill=tk.X)

    def _create_deeplabcut_training_frame(self):
        self.deeplabcut_training_frame = tk.Frame(self.main_frame)
        self.deeplabcut_training_frame.pack(fill=tk.X, pady=5)

        self.deeplabcut_epochs_label = tk.Label(self.deeplabcut_training_frame, text="Epochs:")
        self.deeplabcut_epochs_label.pack(side=tk.LEFT, padx=5)

        self.deeplabcut_epochs_spinbox = tk.Spinbox(self.deeplabcut_training_frame, from_=1, to=1000, textvariable=self.deeplabcut_epochs_var)
        self.deeplabcut_epochs_spinbox.pack(side=tk.LEFT, padx=5)

        self.deeplabcut_save_epochs_label = tk.Label(self.deeplabcut_training_frame, text="Save Epochs:")
        self.deeplabcut_save_epochs_label.pack(side=tk.LEFT, padx=5)

        self.deeplabcut_save_epochs_spinbox = tk.Spinbox(self.deeplabcut_training_frame, from_=1, to=1000, textvariable=self.deeplabcut_save_epochs_var)
        self.deeplabcut_save_epochs_spinbox.pack(side=tk.LEFT, padx=5)

        self.deeplabcut_batch_size_label = tk.Label(self.deeplabcut_training_frame, text="Batch Size:")
        self.deeplabcut_batch_size_label.pack(side=tk.LEFT, padx=5) 

        self.deeplabcut_batch_size_spinbox = tk.Spinbox(self.deeplabcut_training_frame, from_=1, to=1000, textvariable=self.deeplabcut_batch_size_var)
        self.deeplabcut_batch_size_spinbox.pack(side=tk.LEFT, padx=5)

    def _create_videos_frame(self):
        self.load_videos_frame = tk.Frame(self.main_frame)
        self.load_videos_frame.pack(fill=tk.X, pady=5)

        self.load_videos_button = tk.Button(self.load_videos_frame, text="Load Videos")
        self.load_videos_button.pack(side=tk.LEFT, padx=5)

        self.open_videos_button = tk.Button(self.load_videos_frame, text="Open Videos")
        self.open_videos_button.pack(side=tk.LEFT, padx=5)
        self.open_videos_button.config(state=tk.DISABLED)

        self.videos_directory_label = tk.Label(self.load_videos_frame, textvariable=self.videos_directory_path_var, wraplength=400)
        self.videos_directory_label.pack(side=tk.LEFT, padx=5)

    def _create_playback_section(self):
        self.playback_frame = tk.Frame(self.main_frame)
        self.playback_frame.pack(fill=tk.X, pady=5)

        # Control buttons
        control_frame = tk.Frame(self.playback_frame)
        control_frame.pack(fill=tk.X)

        self.play_button = tk.Button(control_frame, text="Play")
        self.play_button.pack(side=tk.LEFT, padx=5)

        self.pause_button = tk.Button(control_frame, text="Pause")
        self.pause_button.pack(side=tk.LEFT, padx=5)

        # Step size and label in its own frame
        step_frame = tk.Frame(self.playback_frame)
        step_frame.pack(fill=tk.X, pady=2)

        step_label = tk.Label(step_frame, text="Step Size:")
        step_label.pack(side=tk.LEFT, padx=5)

        self.step_size_spinbox = tk.Spinbox(step_frame, from_=1, to=100, width=5)
        self.step_size_spinbox.pack(side=tk.LEFT, padx=5)

        # Frame slider in its own frame
        slider_frame = tk.Frame(self.playback_frame)
        slider_frame.pack(fill=tk.X, pady=2)

        self.frame_number_slider.config(length=200)  # Set width to match sidebar
        self.frame_number_slider.pack(fill=tk.X, padx=5, pady=5)

        # FPS control
        fps_frame = tk.Frame(self.playback_frame)
        fps_frame.pack(fill=tk.X, pady=2)

        self.frames_per_second_var.config(length=200)  # Set width to match sidebar
        self.frames_per_second_var.pack(fill=tk.X, padx=5, pady=5)

    def _create_save_option_frame(self):
        """Create the options section with auto-save and save button."""
        self.save_options_frame = tk.Frame(self.main_frame)
        self.save_options_frame.pack(fill=tk.X, pady=5)

        self.autosave_checkbox = tk.Checkbutton(
            self.save_options_frame,
            text="Auto Save",
            variable=self.autosave_boolean_var,
        )
        self.autosave_checkbox.pack(side=tk.LEFT)

        self.save_session_button = tk.Button(
            self.save_options_frame,
            text="Save Session",
        )
        self.save_session_button.pack(side=tk.LEFT, padx=10)

        self.load_session_button = tk.Button(
            self.save_options_frame,
            text="Load Session",
        )
        self.load_session_button.pack(side=tk.LEFT, padx=10)

        self.clear_session_button = tk.Button(
            self.save_options_frame,
            text="Clear Session",
        )
        self.clear_session_button.pack(side=tk.LEFT, padx=5)

        data_handling_frame = tk.Frame(self.main_frame)
        data_handling_frame.pack(fill=tk.X, pady=5)
        self.load_click_data_button = tk.Button(
            data_handling_frame,
            text="Load Click Data",
        )
        self.load_click_data_button.pack(side=tk.LEFT, padx=5)

        self.clear_click_data_button = tk.Button(
            data_handling_frame,
            text="Clear Click Data",
        )
        self.clear_click_data_button.pack(side=tk.LEFT, padx=5)

        self.load_machine_labels_button = tk.Button(
            data_handling_frame,
            text="Load Machine Labels",
        )
        self.load_machine_labels_button.pack(side=tk.LEFT, padx=5)
        self.clear_machine_labels_button = tk.Button(
            data_handling_frame,
            text="Clear Machine Labels",
        )
        self.clear_machine_labels_button.pack(side=tk.LEFT, padx=5)



        # Path label in its own frame for better display
        path_frame = tk.Frame(self.main_frame)
        path_frame.pack(fill=tk.X, pady=2)

        path_label = tk.Label(path_frame, text="Active Click Data Path:")
        path_label.pack(anchor='w', padx=5)

        self.click_save_path_label = tk.Label(
            path_frame,
            textvariable=self.click_save_path_var,
            wraplength=400,  # Wrap text to fit sidebar
        )
        self.click_save_path_label.pack(fill=tk.X, padx=5, pady=2)


        machine_path_label = tk.Label(path_frame, text="Active Machine Labels Path:")
        machine_path_label.pack(anchor='w', padx=5)

        self.machine_labels_path_label = tk.Label(
            path_frame,
            textvariable=self.machine_labels_path_var,
            wraplength=400,  # Wrap text to fit sidebar
        )
        self.machine_labels_path_label.pack(fill=tk.X, padx=5, pady=2)

    def _create_show_help_frame(self):
        """Create the help section."""
        self.show_help_frame = tk.Frame(self.main_frame)
        self.show_help_frame.pack(fill=tk.X, pady=5)

        self.show_help_checkbox = tk.Checkbutton(
            self.show_help_frame,
            text="Show Help",
            variable=self.show_help_boolean_var,
        )
        self.show_help_checkbox.pack(fill=tk.X)

    def _create_progress_frame(self):
        """Create the progress section."""
        self.progress_frame = tk.Frame(self.main_frame)
        self.progress_frame.pack(fill=tk.X, pady=5)

        self.progress_label = tk.Label(self.progress_frame, text="Labeling Progress:")
        self.progress_label.pack(anchor='w', padx=5)

        # Create a LabelingProgress instance
        self.labeling_progress = LabelingProgress(total_rows=self.total_rows_var.get(), labeled_rows=[], master=self.progress_frame)
        self.labeling_progress.pack(fill=tk.X, padx=5, pady=5)

    def set_app_icon(self):
        """
        Set the application icon for the window across different platforms.

        Args:
            root: The main Tk root window that needs the icon
        """
        system = platform.system()

        try:
            if system == "Windows":
                # Windows uses .ico files
                if Path(SKELLYCLICKER_LOGO_ICO).exists():
                    self.root.iconbitmap(SKELLYCLICKER_LOGO_ICO)
                else:
                    logger.warning(f"Windows icon file not found at {SKELLYCLICKER_LOGO_ICO}")

            elif system == "Darwin" or system == "Linux" or True:  # macOS, Linux, or fallback
                # Both macOS and Linux can use the PhotoImage approach
                if Path(SKELLYCLICKER_LOGO_PNG).exists():
                    # Load the logo image
                    logo_img = Image.open(SKELLYCLICKER_LOGO_PNG)
                    # Convert to PhotoImage that tkinter can display
                    icon = ImageTk.PhotoImage(logo_img)
                    # Set as window icon
                    self.root.iconphoto(True, icon)

                    # For macOS, this doesn't change the dock icon.
                    # That would require bundling as a .app with py2app
                else:
                    logger.warning(f"PNG icon file not found at {SKELLYCLICKER_LOGO_PNG}")

        except Exception as e:
            logger.error(f"Error setting app icon: {e} - continuing without")