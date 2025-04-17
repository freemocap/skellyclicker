import os

from pathlib import Path

from deeplabcut.core.engine import Engine
from deeplabcut.utils import auxiliaryfunctions

HUMAN_EXPERIMENTER_NAME: str = "human"


def create_new_deeplabcut_project(
        project_name: str,
        project_parent_directory: str,
        multianimal: bool = False,
        individuals: list[str] | None = None,
        bodyparts: list[str] | None = None,
        skeleton: list[list[str]] | None = None,
):
    ##NOTE: this function is a modified version of the DLC one, did not update the docstrings below - Aaron
    ## NOTE2 (JSM) - And then I came along and nuked big chunks of the original code so that only the parts we need remain
    r"""Create the necessary folders and files for a new project without requiring videos.

    Creating a new project involves creating the project directory, sub-directories and
    a basic configuration file. The configuration file is loaded with the default
    values. Change its parameters to your projects need.

    Parameters
    ----------
    project_name : string
        The name of the project.

    experimenter : string
        The name of the experimenter.

    video_paths : list[str] | None, optional
        A list of strings representing the full paths of the videos to include in the
        project. If the strings represent a directory instead of a file, all videos of
        ``videotype`` will be imported. If None, the project will be created without videos.

    project_parent_directory : string, optional
        The directory where the project will be created. The default is the
        ``current working directory``.

    multianimal: bool, optional. Default: False.
        For creating a multi-animal project (introduced in DLC 2.2)

    individuals: list[str]|None = None,
        Relevant only if multianimal is True.
        list of individuals to be used in the project configuration.
        If None - defaults to ['individual1', 'individual2', 'individual3']
        
    bodyparts: list[str]|None = None,
        Custom list of bodyparts to be tracked.
        If None - defaults to ['bodypart1', 'bodypart2', 'bodypart3', 'objectA'] for single animal
        or ['bodypart1', 'bodypart2', 'bodypart3'] for multi-animal projects.
        
    skeleton: list[list[str]]|None = None,
        Custom skeleton defining connections between bodyparts for visualization.
        Each connection is defined as a list of two bodypart names.
        If None - uses default skeleton connections based on default bodyparts.

    Returns
    -------
    str
        Path to the new project configuration file.

    """

    project_parent_directory = Path(project_parent_directory).resolve()
    project_name = project_name
    project_path = project_parent_directory / project_name

    # Create project and sub-directories
    if project_path.exists() and (project_path / "config.yaml").is_file():
        print('Project "{}" already exists!'.format(project_path))
        return os.path.join(str(project_path), "config.yaml")

    # Create main directories
    data_path = project_path / "labeled-data"
    shuffles_path = project_path / "training-datasets"
    results_path = project_path / "dlc-models"

    # Create standard top-level directories
    for p in [data_path, shuffles_path, results_path]:
        p.mkdir(parents=True, exist_ok=True)
        print('Created "{}"'.format(p))

    # Create default subdirectories for training-datasets
    iteration_path = shuffles_path / "iteration-0"
    iteration_path.mkdir(parents=True, exist_ok=True)
    print('Created "{}"'.format(iteration_path))

    # Create default subdirectories for dlc-models
    model_iteration_path = results_path / "iteration-0"
    model_iteration_path.mkdir(parents=True, exist_ok=True)
    print('Created "{}"'.format(model_iteration_path))

    # Default model path
    model_type_path = model_iteration_path / "ResNet_50"
    model_type_path.mkdir(parents=True, exist_ok=True)
    print('Created "{}"'.format(model_type_path))

    # Set values to config file:
    config_file_contents = _create_deeplabcut_config(bodyparts=bodyparts,
                                                     individuals=individuals,
                                                     multianimal=multianimal,
                                                     project_name=project_name,
                                                     project_path=str(project_path),
                                                     skeleton=skeleton)

    project_config_file_path = os.path.join(str(project_path), "config.yaml")
    # Write dictionary to yaml config file
    auxiliaryfunctions.write_config(project_config_file_path, config_file_contents)

    print('Generated "{}"'.format(project_path / "config.yaml"))
    print(
        "\nA new project with name %s is created at %s and a configurable file (config.yaml) is stored there. Change the parameters in this file to adapt to your project's needs.\n Once you have changed the configuration file, use the function 'extract_frames' to select frames for labeling.\n. [OPTIONAL] Use the function 'add_new_videos' to add new videos to your project (at any stage)."
        % (project_name, str(project_parent_directory))
    )

    if bodyparts is not None:
        print(f"\nUsing bodyparts: {bodyparts}")

    if skeleton is not None:
        print(f"\nUsing custom skeleton configuration with {len(skeleton)} connections")

    print(f"Created project at: {project_path}")

    return project_config_file_path


def _create_deeplabcut_config(project_path: str,
                              project_name: str,
                              multianimal: bool = False,
                              individuals: list[str] | None = None,
                              bodyparts: list[str] | None = None,
                              skeleton: list[list[str]] | None = None):
    if multianimal:  # parameters specific to multi-animal project
        config_file_contents = _initialize_multi_animal_config(bodyparts=bodyparts,
                                                               individuals=individuals,
                                                               multianimal=multianimal,
                                                               skeleton=skeleton)
    else:
        config_file_contents = _initialize_default_config(bodyparts=bodyparts,
                                                          skeleton=skeleton)
    _add_shared_config_parameters(config_file_contents=config_file_contents,
                                  project_name=project_name,
                                  project_path=project_path)
    return config_file_contents


def _add_shared_config_parameters(config_file_contents: dict[str, object],
                                  project_name: str,
                                  project_path: str):
    # common parameters:
    config_file_contents["Task"] = project_name
    config_file_contents["scorer"] = HUMAN_EXPERIMENTER_NAME
    config_file_contents["project_path"] = str(project_path)
    config_file_contents[
        "date"] = '_'  ##NOTE: Find some way to get rid of this 04/02/25 AARON (need to adjust 'get_training_set_folder' in 'auxilliary functions' of deeplabcut)
    config_file_contents["cropping"] = False
    config_file_contents["start"] = 0
    config_file_contents["stop"] = 1
    config_file_contents["numframes2pick"] = 20
    config_file_contents["TrainingFraction"] = [0.95]
    config_file_contents["iteration"] = 0
    config_file_contents["snapshotindex"] = -1
    config_file_contents["detector_snapshotindex"] = -1
    config_file_contents["x1"] = 0
    config_file_contents["x2"] = 640
    config_file_contents["y1"] = 277
    config_file_contents["y2"] = 624
    config_file_contents["batch_size"] = 8  # batch size during inference (video - analysis)
    config_file_contents["detector_batch_size"] = 1
    config_file_contents["corner2move2"] = (50, 50)
    config_file_contents["move2corner"] = True
    config_file_contents["skeleton_color"] = "black"
    config_file_contents["pcutoff"] = 0.6
    config_file_contents["dotsize"] = 12  # for plots size of dots
    config_file_contents["alphavalue"] = 0.7  # for plots transparency of markers
    config_file_contents["colormap"] = "rainbow"  # for plots type of colormap


def _initialize_default_config(bodyparts: list[str],
                               skeleton: list[list[str]] | None = None) -> dict[str, object]:
    config_file_contents, _ = auxiliaryfunctions.create_config_template()
    config_file_contents["multianimalproject"] = False
    config_file_contents["video_sets"] = {}
    # Use custom bodyparts if provided, otherwise use defaults
    default_sa_bodyparts = ["bodypart1", "bodypart2", "bodypart3", "objectA"]
    config_file_contents["bodyparts"] = bodyparts if bodyparts is not None else default_sa_bodyparts
    # Use custom skeleton if provided, otherwise generate default based on bodyparts
    if skeleton is not None:
        config_file_contents["skeleton"] = skeleton
    else:
        # Generate default skeleton based on the bodyparts
        bp = config_file_contents["bodyparts"]
        if len(bp) >= 4:
            config_file_contents["skeleton"] = [[bp[0], bp[1]], [bp[3], bp[2]]]
        elif len(bp) == 3:
            config_file_contents["skeleton"] = [[bp[0], bp[1]], [bp[1], bp[2]]]
        elif len(bp) == 2:
            config_file_contents["skeleton"] = [[bp[0], bp[1]]]
        else:
            config_file_contents["skeleton"] = []  # Can't make connections with less than 2 bodyparts
    config_file_contents["default_augmenter"] = "default"
    config_file_contents["default_net_type"] = "resnet_50"
    return config_file_contents


def _initialize_multi_animal_config(bodyparts: list[str],
                                    individuals: list[str],
                                    multianimal: bool,
                                    skeleton: list[list[str]]) -> dict[str, object]:
    config_file_contents, _ = auxiliaryfunctions.create_config_template(multianimal)
    config_file_contents["multianimalproject"] = multianimal
    config_file_contents["identity"] = False
    config_file_contents["individuals"] = (
        individuals
        if individuals
        else ["individual1", "individual2", "individual3"]
    )
    # Use custom bodyparts if provided, otherwise use defaults
    default_ma_bodyparts = ["bodypart1", "bodypart2", "bodypart3"]
    config_file_contents["multianimalbodyparts"] = bodyparts if bodyparts is not None else default_ma_bodyparts
    config_file_contents["uniquebodyparts"] = []
    config_file_contents["bodyparts"] = "MULTI!"
    # Use custom skeleton if provided, otherwise generate default based on bodyparts
    if skeleton is not None:
        config_file_contents["skeleton"] = skeleton
    else:
        # Generate default skeleton based on the bodyparts
        bp = config_file_contents["multianimalbodyparts"]
        if len(bp) >= 3:
            config_file_contents["skeleton"] = [
                [bp[0], bp[1]],
                [bp[1], bp[2]],
                [bp[0], bp[2]],
            ]
        elif len(bp) == 2:
            config_file_contents["skeleton"] = [[bp[0], bp[1]]]
        else:
            config_file_contents["skeleton"] = []  # Can't make connections with less than 2 bodyparts
    engine = config_file_contents.get("engine")
    if engine in Engine.PYTORCH.aliases:
        config_file_contents["default_augmenter"] = "albumentations"
        config_file_contents["default_net_type"] = "resnet_50"
    elif engine in Engine.TF.aliases:
        config_file_contents["default_augmenter"] = "multi-animal-imgaug"
        config_file_contents["default_net_type"] = "dlcrnet_ms5"
    else:
        raise ValueError(f"Unknown or undefined engine {engine}")
    config_file_contents["default_track_method"] = "ellipse"
    return config_file_contents


if __name__ == '__main__':
    from pathlib import Path

    create_new_deeplabcut_project(
        project_name='your-project-name',
        project_parent_directory=str(Path().home() / 'test_dlc'),
        bodyparts=['head', 'shoulder', 'elbow', 'wrist', 'finger'],
        skeleton=[['head', 'shoulder'], ['shoulder', 'elbow'],
                  ['elbow', 'wrist'], ['wrist', 'finger']]
    )
