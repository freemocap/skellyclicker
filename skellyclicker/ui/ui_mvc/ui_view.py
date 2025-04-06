import tkinter as tk
from dataclasses import dataclass, field


@dataclass
class SkellyClickerUIView:
    main_frame: tk.Frame = None

    # Load videos section
    videos_directory_path_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="No videos loaded"))
    load_videos_frame: tk.Frame = None
    load_videos_button: tk.Button = None
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

    # Save section
    save_options_frame: tk.Frame = None
    autosave_checkbox: tk.Checkbutton = None
    autosave_boolean_var: tk.BooleanVar = field(default_factory=tk.BooleanVar)
    click_save_path_var: tk.StringVar = field(default_factory=lambda: tk.StringVar(value="No file saved"))
    click_save_path_label: tk.Label = None
    save_csv_button: tk.Button = None
    clear_session_button: tk.Button = None

    # Info section
    show_help_frame: tk.Frame = None
    show_help_boolean_var: tk.BooleanVar = field(default_factory=tk.BooleanVar)
    show_help_checkbox: tk.Checkbutton = None

    @classmethod
    def create_ui(cls, root: tk.Tk):
        """Create the main UI frame."""
        instance = cls()
        instance.main_frame = tk.Frame(root)
        instance.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create sections
        instance._create_deeplabcut_frame()
        instance._create_separator()
        instance._create_videos_frame()
        instance._create_separator()
        instance._create_playback_section()
        instance._create_separator()
        instance._create_save_option_frame()
        instance._create_separator()
        instance._create_show_help_frame()
        return instance


    def _create_separator(self):
        """Create a separator line."""
        separator = tk.Frame(self.main_frame, height=2, bd=1, relief=tk.SUNKEN)
        separator.pack(fill=tk.X, padx=5, pady=5)
        return separator

    def _create_deeplabcut_frame(self):
        self.deeplabcut_frame = tk.Frame(self.main_frame)
        self.deeplabcut_frame.pack(fill=tk.X, pady=5)

        self.load_deeplabcut_button = tk.Button(self.deeplabcut_frame, text="Load")
        self.load_deeplabcut_button.pack(side=tk.LEFT, padx=5)

        self.create_deeplabcut_button = tk.Button(self.deeplabcut_frame, text="Create")
        self.create_deeplabcut_button.pack(side=tk.LEFT, padx=5)

        self.deeplabcut_project_label = tk.Label(self.deeplabcut_frame, text="Deeplabcut Project")
        self.deeplabcut_project_label.pack(side=tk.LEFT, padx=5)
        self.deeplabcut_project_label.pack(fill=tk.X)

        self.train_deeplabcut_model_button = tk.Button(self.deeplabcut_frame, text="Train DLC Model")
        self.train_deeplabcut_model_button.pack(side=tk.LEFT, padx=5)

    def _create_videos_frame(self):
        self.load_videos_frame = tk.Frame(self.main_frame)
        self.load_videos_frame.pack(fill=tk.X, pady=5)

        self.load_videos_button = tk.Button(self.load_videos_frame, text="Load Videos")
        self.load_videos_button.pack(side=tk.LEFT, padx=5)

        self.videos_directory_label = tk.Label(self.load_videos_frame, textvariable=self.videos_directory_path_var)
        self.videos_directory_label.pack(side=tk.LEFT, padx=5)

    def _create_playback_section(self):
        self.playback_frame = tk.Frame(self.main_frame)
        self.playback_frame.pack(fill=tk.X, pady=5)
        self.play_button = tk.Button(self.playback_frame, text="Play")
        self.play_button.pack(side=tk.LEFT, padx=5)
        self.pause_button = tk.Button(self.playback_frame, text="Pause")
        self.pause_button.pack(side=tk.LEFT, padx=5)
        self.step_size_spinbox = tk.Spinbox(self.playback_frame, from_=1, to=100)
        self.step_size_spinbox.pack(side=tk.LEFT, padx=5)
        self.frame_number_slider.pack(side=tk.LEFT, padx=5)

    def _create_save_option_frame(self):
        """Create the options section with auto-save and save button."""
        self.save_options_frame = tk.Frame(self.main_frame)
        self.save_options_frame.pack(fill=tk.X, pady=5)

        self.autosave_checkbox = tk.Checkbutton(
            self.save_options_frame,
            text="Auto",
            variable=self.autosave_boolean_var,
        )
        self.autosave_checkbox.pack(side=tk.LEFT)

        self.save_csv_button = tk.Button(
            self.save_options_frame,
            text="Save Labels to CSV",
        )
        self.save_csv_button.pack(side=tk.LEFT, padx=10)

        self.click_save_path_label = tk.Label(
            self.save_options_frame,
            textvariable=self.click_save_path_var,
        )
        self.click_save_path_label.pack(side=tk.LEFT, padx=5)

        self.clear_session_button = tk.Button(
            self.save_options_frame,
            text="Clear Session",
        )
        self.clear_session_button.pack(side=tk.LEFT, padx=5)

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

    def _create_clear_session_frame(self):
        """Create the session clearing section."""
        self.clear_frame = tk.Frame(self.main_frame)
        self.clear_frame.pack(fill=tk.X, pady=5)

        self.clear_btn = tk.Button(
            self.clear_frame,
            text="Clear Session",
        )
        self.clear_btn.pack(fill=tk.X)

