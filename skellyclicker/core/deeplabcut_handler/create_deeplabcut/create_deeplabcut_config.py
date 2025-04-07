from datetime import datetime
from pathlib import Path

def create_new_project(
    project: str,
    experimenter: str,
    videos: list[str] | None = None,
    working_directory: str | Path | None = None,
    copy_videos: bool = False,
    videotype: str = "",
    multianimal: bool = False,
    individuals: list[str] | None = None,
    bodyparts: list[str] | None = None,
    skeleton: list[list[str]] | None = None,
):
    ##NOTE: this function is a modified version of the DLC one, did not update the docstrings below - Aaron
    r"""Create the necessary folders and files for a new project without requiring videos.

    Creating a new project involves creating the project directory, sub-directories and
    a basic configuration file. The configuration file is loaded with the default
    values. Change its parameters to your projects need.

    Parameters
    ----------
    project : string
        The name of the project.

    experimenter : string
        The name of the experimenter.

    videos : list[str] | None, optional
        A list of strings representing the full paths of the videos to include in the
        project. If the strings represent a directory instead of a file, all videos of
        ``videotype`` will be imported. If None, the project will be created without videos.

    working_directory : string, optional
        The directory where the project will be created. The default is the
        ``current working directory``.

    copy_videos : bool, optional, Default: False.
        If True, the videos are copied to the ``videos`` directory. If False, symlinks
        of the videos will be created in the ``project/videos`` directory; in the event
        of a failure to create symbolic links, videos will be moved instead.

    videotype : string, optional
        The extension of the video files to include. Only relevant if videos contains
        directories.

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

    Examples
    --------

    Create a project without videos:

    >>> deeplabcut.create_new_project(
            project='reaching-task',
            experimenter='Linus',
            working_directory='/analysis/project/',
        )

    Create a project with videos:

    >>> deeplabcut.create_new_project(
            project='reaching-task',
            experimenter='Linus',
            videos=[
                '/data/videos/mouse1.avi',
                '/data/videos/mouse2.avi',
                '/data/videos/mouse3.avi'
            ],
            working_directory='/analysis/project/',
        )
    """
    from datetime import datetime as dt
    from deeplabcut.utils import auxiliaryfunctions
    import os
    import shutil
    import warnings

    from deeplabcut import DEBUG
    from deeplabcut.core.engine import Engine

    # Try to import VideoReader only if videos are provided
    if videos:
        try:
            from deeplabcut.utils.auxfun_videos import VideoReader
        except ImportError:
            warnings.warn("VideoReader could not be imported. Video-related functionality will be limited.")
            



    if working_directory is None:
        working_directory = "."
    wd = Path(working_directory).resolve()
    project_name = project
    project_path = wd / project_name

    # Create project and sub-directories
    if not DEBUG and project_path.exists():
        print('Project "{}" already exists!'.format(project_path))
        return os.path.join(str(project_path), "config.yaml")
    
    # Create main directories
    video_path = project_path / "videos"
    data_path = project_path / "labeled-data"
    shuffles_path = project_path / "training-datasets"
    results_path = project_path / "dlc-models"
    
    # Create standard top-level directories
    for p in [video_path, data_path, shuffles_path, results_path]:
        p.mkdir(parents=True, exist_ok=DEBUG)
        print('Created "{}"'.format(p))
    
    # Create common subdirectories for training-datasets
    iteration_path = shuffles_path / "iteration-0"
    iteration_path.mkdir(parents=True, exist_ok=DEBUG)
    print('Created "{}"'.format(iteration_path))
    
    # Create common subdirectories for dlc-models
    model_iteration_path = results_path / "iteration-0"
    model_iteration_path.mkdir(parents=True, exist_ok=DEBUG)
    print('Created "{}"'.format(model_iteration_path))
    
    # Default model path (will depend on config settings, but creating a common one)
    model_type_path = model_iteration_path / "ResNet_50"
    model_type_path.mkdir(parents=True, exist_ok=DEBUG)
    print('Created "{}"'.format(model_type_path))

    # Initialize video_sets
    video_sets = {}
    
    # Process videos only if they're provided
    if videos:
        # Add all videos in the folder. Multiple folders can be passed in a list, similar to the video files. Folders and video files can also be passed!
        vids = []
        for i in videos:
            # Check if it is a folder
            if os.path.isdir(i):
                vids_in_dir = [
                    os.path.join(i, vp)
                    for vp in os.listdir(i)
                    if vp.lower().endswith(videotype)
                ]
                vids = vids + vids_in_dir
                if len(vids_in_dir) == 0:
                    print("No videos found in", i)
                    print(
                        "Perhaps change the videotype, which is currently set to:",
                        videotype,
                    )
                else:
                    videos = vids
                    print(
                        len(vids_in_dir),
                        " videos from the directory",
                        i,
                        "were added to the project.",
                    )
            else:
                if os.path.isfile(i):
                    vids = vids + [i]
                videos = vids

        videos = [Path(vp) for vp in videos]
        dirs = [data_path / Path(i.stem) for i in videos]
        for p in dirs:
            """
            Creates directory under data
            """
            p.mkdir(parents=True, exist_ok=True)

        destinations = [video_path.joinpath(vp.name) for vp in videos]
        if copy_videos:
            print("Copying the videos")
            for src, dst in zip(videos, destinations):
                shutil.copy(
                    os.fspath(src), os.fspath(dst)
                )  # https://www.python.org/dev/peps/pep-0519/
        else:
            # creates the symlinks of the video and puts it in the videos directory.
            print("Attempting to create a symbolic link of the video ...")
            for src, dst in zip(videos, destinations):
                if dst.exists() and not DEBUG:
                    raise FileExistsError("Video {} exists already!".format(dst))
                try:
                    src = str(src)
                    dst = str(dst)
                    os.symlink(src, dst)
                    print("Created the symlink of {} to {}".format(src, dst))
                except OSError:
                    try:
                        import subprocess

                        subprocess.check_call("mklink %s %s" % (dst, src), shell=True)
                    except (OSError, subprocess.CalledProcessError):
                        print(
                            "Symlink creation impossible (exFat architecture?): "
                            "copying the video instead."
                        )
                        shutil.copy(os.fspath(src), os.fspath(dst))
                        print("{} copied to {}".format(src, dst))
                videos = destinations

        if copy_videos:
            videos = destinations  # in this case the *new* location should be added to the config file

        # adds the video list to the config.yaml file
        for video in videos:
            print(video)
            try:
                # For windows os.path.realpath does not work and does not link to the real video. [old: rel_video_path = os.path.realpath(video)]
                rel_video_path = str(Path.resolve(Path(video)))
            except:
                rel_video_path = os.readlink(str(video))

            try:
                if 'VideoReader' in locals():
                    vid = VideoReader(rel_video_path)
                    video_sets[rel_video_path] = {"crop": ", ".join(map(str, vid.get_bbox()))}
                else:
                    # If VideoReader couldn't be imported, we'll just add the video without crop info
                    video_sets[rel_video_path] = {"crop": "0, 640, 0, 480"}  # Default values
            except IOError:
                warnings.warn("Cannot open the video file! Skipping to the next one...")
                if os.path.exists(video):
                    os.remove(video)  # Removing the video or link from the project

        # Only check for valid videos if videos were provided
        if not len(video_sets) and videos:
            # Silently sweep the files that were already written.
            shutil.rmtree(project_path, ignore_errors=True)
            warnings.warn(
                "No valid videos were found. The project was not created... "
                "Verify the video files and re-create the project."
            )
            return "nothingcreated"

    # Set values to config file:
    if multianimal:  # parameters specific to multianimal project
        cfg_file, ruamelFile = auxiliaryfunctions.create_config_template(multianimal)
        cfg_file["multianimalproject"] = multianimal
        cfg_file["identity"] = False
        cfg_file["individuals"] = (
            individuals
            if individuals
            else ["individual1", "individual2", "individual3"]
        )
        
        # Use custom bodyparts if provided, otherwise use defaults
        default_ma_bodyparts = ["bodypart1", "bodypart2", "bodypart3"]
        cfg_file["multianimalbodyparts"] = bodyparts if bodyparts is not None else default_ma_bodyparts
        cfg_file["uniquebodyparts"] = []
        cfg_file["bodyparts"] = "MULTI!"
        
        # Use custom skeleton if provided, otherwise generate default based on bodyparts
        if skeleton is not None:
            cfg_file["skeleton"] = skeleton
        else:
            # Generate default skeleton based on the bodyparts
            bp = cfg_file["multianimalbodyparts"]
            if len(bp) >= 3:
                cfg_file["skeleton"] = [
                    [bp[0], bp[1]],
                    [bp[1], bp[2]],
                    [bp[0], bp[2]],
                ]
            elif len(bp) == 2:
                cfg_file["skeleton"] = [[bp[0], bp[1]]]
            else:
                cfg_file["skeleton"] = []  # Can't make connections with less than 2 bodyparts
        
        engine = cfg_file.get("engine")
        if engine in Engine.PYTORCH.aliases:
            cfg_file["default_augmenter"] = "albumentations"
            cfg_file["default_net_type"] = "resnet_50"
        elif engine in Engine.TF.aliases:
            cfg_file["default_augmenter"] = "multi-animal-imgaug"
            cfg_file["default_net_type"] = "dlcrnet_ms5"
        else:
            raise ValueError(f"Unknown or undefined engine {engine}")
        cfg_file["default_track_method"] = "ellipse"
    else:
        cfg_file, ruamelFile = auxiliaryfunctions.create_config_template()
        cfg_file["multianimalproject"] = False
        
        # Use custom bodyparts if provided, otherwise use defaults
        default_sa_bodyparts = ["bodypart1", "bodypart2", "bodypart3", "objectA"]
        cfg_file["bodyparts"] = bodyparts if bodyparts is not None else default_sa_bodyparts
        
        # Use custom skeleton if provided, otherwise generate default based on bodyparts
        if skeleton is not None:
            cfg_file["skeleton"] = skeleton
        else:
            # Generate default skeleton based on the bodyparts
            bp = cfg_file["bodyparts"]
            if len(bp) >= 4:
                cfg_file["skeleton"] = [[bp[0], bp[1]], [bp[3], bp[2]]]
            elif len(bp) == 3:
                cfg_file["skeleton"] = [[bp[0], bp[1]], [bp[1], bp[2]]]
            elif len(bp) == 2:
                cfg_file["skeleton"] = [[bp[0], bp[1]]]
            else:
                cfg_file["skeleton"] = []  # Can't make connections with less than 2 bodyparts
                
        cfg_file["default_augmenter"] = "default"
        cfg_file["default_net_type"] = "resnet_50"

    # common parameters:
    cfg_file["Task"] = project
    cfg_file["scorer"] = experimenter
    cfg_file["video_sets"] = video_sets
    cfg_file["project_path"] = str(project_path)
    cfg_file["date"] = '_' ##NOTE: Find some way to get rid of this 04/02/25 AARON (need to adjust 'get_training_set_folder' in 'auxilliary functions' of deeplabcut)
    cfg_file["cropping"] = False
    cfg_file["start"] = 0
    cfg_file["stop"] = 1
    cfg_file["numframes2pick"] = 20
    cfg_file["TrainingFraction"] = [0.95]
    cfg_file["iteration"] = 0
    cfg_file["snapshotindex"] = -1
    cfg_file["detector_snapshotindex"] = -1
    cfg_file["x1"] = 0
    cfg_file["x2"] = 640
    cfg_file["y1"] = 277
    cfg_file["y2"] = 624
    cfg_file["batch_size"] = 8  # batch size during inference (video - analysis)
    cfg_file["detector_batch_size"] = 1
    cfg_file["corner2move2"] = (50, 50)
    cfg_file["move2corner"] = True
    cfg_file["skeleton_color"] = "black"
    cfg_file["pcutoff"] = 0.6
    cfg_file["dotsize"] = 12  # for plots size of dots
    cfg_file["alphavalue"] = 0.7  # for plots transparency of markers
    cfg_file["colormap"] = "rainbow"  # for plots type of colormap

    projconfigfile = os.path.join(str(project_path), "config.yaml")
    # Write dictionary to yaml config file
    auxiliaryfunctions.write_config(projconfigfile, cfg_file)

    print('Generated "{}"'.format(project_path / "config.yaml"))
    print(
        "\nA new project with name %s is created at %s and a configurable file (config.yaml) is stored there. Change the parameters in this file to adapt to your project's needs.\n Once you have changed the configuration file, use the function 'extract_frames' to select frames for labeling.\n. [OPTIONAL] Use the function 'add_new_videos' to add new videos to your project (at any stage)."
        % (project_name, str(wd))
    )
    
    # Different message if no videos were provided
    if not videos:
        print("\nNote: No videos were added to this project. You can add videos later using the 'add_new_videos' function.")
    
    # Print message about custom bodyparts if provided
    if bodyparts is not None:
        print(f"\nUsing custom bodyparts: {bodyparts}")
        
    # Print message about custom skeleton if provided  
    if skeleton is not None:
        print(f"\nUsing custom skeleton configuration with {len(skeleton)} connections")
        
    return projconfigfile


if __name__ == '__main__':
    from pathlib import Path

    create_new_project(
        project='your-project-name',
        experimenter='Aaron',
        working_directory= Path(r'C:\Users\Aaron\Documents'),
        bodyparts=['head', 'shoulder', 'elbow', 'wrist', 'finger'],
        skeleton=[['head', 'shoulder'], ['shoulder', 'elbow'], 
                ['elbow', 'wrist'], ['wrist', 'finger']]
    )