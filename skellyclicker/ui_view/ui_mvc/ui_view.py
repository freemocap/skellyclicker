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
    frame_number_slider: tk.Scale = None

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
