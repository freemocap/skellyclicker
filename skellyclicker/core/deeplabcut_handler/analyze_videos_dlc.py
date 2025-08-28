#
# A refactoring of DeepLabCut's PyTorch inference pipeline designed to process a folder of videos in parallel
#
# DeepLabCut Toolbox (deeplabcut.org)
# © A. & M.W. Mathis Labs
# https://github.com/DeepLabCut/DeepLabCut
#
# Please see AUTHORS for contributors.
# https://github.com/DeepLabCut/DeepLabCut/blob/main/AUTHORS
#
# Licensed under GNU Lesser General Public License v3.0
#

from __future__ import annotations
from multiprocessing import Pool

import albumentations as A
import pickle
import time
from pathlib import Path

from deeplabcut.compat import _update_device
from deeplabcut.pose_estimation_pytorch.apis.videos import (
    VideoIterator,
    _generate_metadata,
    video_inference,
)
import deeplabcut.pose_estimation_pytorch.apis.utils as utils
from deeplabcut.pose_estimation_pytorch.apis.videos import (
    _generate_assemblies_file,
    _generate_output_data,
    _validate_destfolder,
    create_df_from_prediction,
)
import deeplabcut.pose_estimation_pytorch.runners.shelving as shelving
from deeplabcut.core.engine import Engine
from deeplabcut.pose_estimation_pytorch.apis.tracklets import (
    convert_detections2tracklets,
)
from deeplabcut.pose_estimation_pytorch.runners import DynamicCropper
from deeplabcut.pose_estimation_pytorch.task import Task
from deeplabcut.refine_training_dataset.stitch import stitch_tracklets
from deeplabcut.utils import auxiliaryfunctions


def analyze_videos(
    config: str,
    videos: list[str],
    videotype: str = "",
    shuffle: int = 1,
    trainingsetindex: int = 0,
    gputouse: int | None = None,
    save_as_csv: bool = False,
    in_random_order: bool = True,
    destfolder: str | None = None,
    batchsize: int | None = None,
    cropping: list[int] | None = None,
    TFGPUinference: bool = True,
    dynamic: tuple[bool, float, int] = (False, 0.5, 10),
    modelprefix: str = "",
    robust_nframes: bool = False,
    allow_growth: bool = False,
    use_shelve: bool = False,
    auto_track: bool = True,
    n_tracks: int | None = None,
    animal_names: list[str] | None = None,
    calibrate: bool = False,
    identity_only: bool = False,
    snapshot_index: int | str | None = None,
    detector_snapshot_index: int | str | None = None,
    device: str | None = None,
    batch_size: int | None = None,
    detector_batch_size: int | None = None,
    transform: A.Compose | None = None,
    overwrite: bool = False,
    save_as_df: bool = False,
    **torch_kwargs,
):
    """Makes prediction based on a trained network.

    The index of the trained network is specified by parameters in the config file
    (in particular the variable 'snapshotindex').

    The labels are stored as MultiIndex Pandas Array, which contains the name of
    the network, body part name, (x, y) label position in pixels, and the
    likelihood for each frame per body part. These arrays are stored in an
    efficient Hierarchical Data Format (HDF) in the same directory where the video
    is stored. However, if the flag save_as_csv is set to True, the data can also
    be exported in comma-separated values format (.csv), which in turn can be
    imported in many programs, such as MATLAB, R, Prism, etc.

    Parameters
    ----------
    config: str
        Full path of the config.yaml file.

    videos: list[str]
        A list of strings containing the full paths to videos for analysis or a path to
        the directory, where all the videos with same extension are stored.

    videotype: str, optional, default=""
        Checks for the extension of the video in case the input to the video is a
        directory. Only videos with this extension are analyzed. If left unspecified,
        videos with common extensions ('avi', 'mp4', 'mov', 'mpeg', 'mkv') are kept.

    shuffle: int, optional, default=1
        An integer specifying the shuffle index of the training dataset used for
        training the network.

    trainingsetindex: int, optional, default=0
        Integer specifying which TrainingsetFraction to use.
        By default the first (note that TrainingFraction is a list in config.yaml).

    gputouse: int or None, optional, default=None
        Only for the TensorFlow engine (for the PyTorch engine see the ``torch_kwargs``:
        you can use ``device``).
        Indicates the GPU to use (see number in ``nvidia-smi``). If you do not have a
        GPU put ``None``.
        See: https://nvidia.custhelp.com/app/answers/detail/a_id/3751/~/useful-nvidia-smi-queries

    save_as_csv: bool, optional, default=False
        Saves the predictions in a .csv file.

    in_random_order: bool, optional (default=True)
        Whether or not to analyze videos in a random order.
        This is only relevant when specifying a video directory in `videos`.

    destfolder: string or None, optional, default=None
        Specifies the destination folder for analysis data. If ``None``, the path of
        the video is used. Note that for subsequent analysis this folder also needs to
        be passed.

    batchsize: int or None, optional, default=None
        Currently not supported by the PyTorch engine.
        Change batch size for inference; if given overwrites value in ``pose_cfg.yaml``.

    cropping: list or None, optional, default=None
        Currently not supported by the PyTorch engine.
        List of cropping coordinates as [x1, x2, y1, y2].
        Note that the same cropping parameters will then be used for all videos.
        If different video crops are desired, run ``analyze_videos`` on individual
        videos with the corresponding cropping coordinates.

    TFGPUinference: bool, optional, default=True
        Only for the TensorFlow engine.
        Perform inference on GPU with TensorFlow code. Introduced in "Pretraining
        boosts out-of-domain robustness for pose estimation" by Alexander Mathis,
        Mert Yüksekgönül, Byron Rogers, Matthias Bethge, Mackenzie W. Mathis.
        Source: https://arxiv.org/abs/1909.11229

    dynamic: tuple(bool, float, int) triple containing (state, det_threshold, margin)
        If the state is true, then dynamic cropping will be performed. That means that
        if an object is detected (i.e. any body part > detectiontreshold), then object
        boundaries are computed according to the smallest/largest x position and
        smallest/largest y position of all body parts. This  window is expanded by the
        margin and from then on only the posture within this crop is analyzed (until the
        object is lost, i.e. <detectiontreshold). The current position is utilized for
        updating the crop window for the next frame (this is why the margin is important
        and should be set large enough given the movement of the animal).

    modelprefix: str, optional, default=""
        Directory containing the deeplabcut models to use when evaluating the network.
        By default, the models are assumed to exist in the project folder.

    robust_nframes: bool, optional, default=False
        Evaluate a video's number of frames in a robust manner.
        This option is slower (as the whole video is read frame-by-frame),
        but does not rely on metadata, hence its robustness against file corruption.

    allow_growth: bool, optional, default=False.
        Only for the TensorFlow engine.
        For some smaller GPUs the memory issues happen. If ``True``, the memory
        allocator does not pre-allocate the entire specified GPU memory region, instead
        starting small and growing as needed.
        See issue: https://forum.image.sc/t/how-to-stop-running-out-of-vram/30551/2

    use_shelve: bool, optional, default=False
        By default, data are dumped in a pickle file at the end of the video analysis.
        Otherwise, data are written to disk on the fly using a "shelf"; i.e., a
        pickle-based, persistent, database-like object by default, resulting in
        constant memory footprint.

    The following parameters are only relevant for multi-animal projects:

    auto_track: bool, optional, default=True
        By default, tracking and stitching are automatically performed, producing the
        final h5 data file. This is equivalent to the behavior for single-animal
        projects.

        If ``False``, one must run ``convert_detections2tracklets`` and
        ``stitch_tracklets`` afterwards, in order to obtain the h5 file.

    This function has 3 related sub-calls:

    identity_only: bool, optional, default=False
        If ``True`` and animal identity was learned by the model, assembly and tracking
        rely exclusively on identity prediction.

    calibrate: bool, optional, default=False
        If ``True``, use training data to calibrate the animal assembly procedure. This
        improves its robustness to wrong body part links, but requires very little
        missing data.

    n_tracks: int or None, optional, default=None
        Number of tracks to reconstruct. By default, taken as the number of individuals
        defined in the config.yaml. Another number can be passed if the number of
        animals in the video is different from the number of animals the model was
        trained on.

    animal_names: list[str], optional
        If you want the names given to individuals in the labeled data file, you can
        specify those names as a list here. If given and `n_tracks` is None, `n_tracks`
        will be set to `len(animal_names)`. If `n_tracks` is not None, then it must be
        equal to `len(animal_names)`. If it is not given, then `animal_names` will
        be loaded from the `individuals` in the project config.yaml file.

    use_openvino: str, optional
        Only for the TensorFlow engine.
        Use "CPU" for inference if OpenVINO is available in the Python environment.

    engine: Engine, optional, default = None.
        The default behavior loads the engine for the shuffle from the metadata. You can
        overwrite this by passing the engine as an argument, but this should generally
        not be done.

    torch_kwargs:
        Any extra parameters to pass to the PyTorch API, such as ``device`` which can
        be used to specify the CUDA device to use for training.

    Returns
    -------
    DLCScorer: str
        the scorer used to analyze the videos

    Examples
    --------

    Analyzing a single video on Windows

    >>> deeplabcut.analyze_videos(
            'C:\\myproject\\reaching-task\\config.yaml',
            ['C:\\yourusername\\rig-95\\Videos\\reachingvideo1.avi'],
        )

    Analyzing a single video on Linux/MacOS

    >>> deeplabcut.analyze_videos(
            '/analysis/project/reaching-task/config.yaml',
            ['/analysis/project/videos/reachingvideo1.avi'],
        )

    Analyze all videos of type ``avi`` in a folder

    >>> deeplabcut.analyze_videos(
            '/analysis/project/reaching-task/config.yaml',
            ['/analysis/project/videos'],
            videotype='.avi',
        )

    Analyze multiple videos

    >>> deeplabcut.analyze_videos(
            '/analysis/project/reaching-task/config.yaml',
            [
                '/analysis/project/videos/reachingvideo1.avi',
                '/analysis/project/videos/reachingvideo2.avi',
            ],
        )

    Analyze multiple videos with ``shuffle=2``

    >>> deeplabcut.analyze_videos(
            '/analysis/project/reaching-task/config.yaml',
            [
                '/analysis/project/videos/reachingvideo1.avi',
                '/analysis/project/videos/reachingvideo2.avi',
            ],
            shuffle=2,
        )

    Analyze multiple videos with ``shuffle=2``, save results as an additional csv file

    >>> deeplabcut.analyze_videos(
            '/analysis/project/reaching-task/config.yaml',
            [
                '/analysis/project/videos/reachingvideo1.avi',
                '/analysis/project/videos/reachingvideo2.avi',
            ],
            shuffle=2,
            save_as_csv=True,
        )
    """
    _update_device(gputouse, torch_kwargs)

    if batchsize is not None:
        if "batch_size" in torch_kwargs:
            print(
                f"You called analyze_videos with parameters ``batchsize={batchsize}"
                f"`` and batch_size={torch_kwargs['batch_size']}. Only one is "
                f"needed/used. Using batch size {torch_kwargs['batch_size']}"
            )
        else:
            torch_kwargs["batch_size"] = batchsize

    # Create the output folder
    _validate_destfolder(destfolder)

    # Load the project configuration
    cfg = auxiliaryfunctions.read_config(config)
    project_path = Path(cfg["project_path"])
    train_fraction = cfg["TrainingFraction"][trainingsetindex]
    model_folder = project_path / auxiliaryfunctions.get_model_folder(
        train_fraction,
        shuffle,
        cfg,
        modelprefix=modelprefix,
        engine=Engine.PYTORCH,
    )
    train_folder = model_folder / "train"

    # Read the inference configuration, load the model
    model_cfg_path = train_folder / Engine.PYTORCH.pose_cfg_name
    model_cfg = auxiliaryfunctions.read_plainconfig(model_cfg_path)
    pose_task = Task(model_cfg["method"])

    pose_cfg_path = model_folder / "test" / "pose_cfg.yaml"
    pose_cfg = auxiliaryfunctions.read_plainconfig(pose_cfg_path)

    snapshot_index, detector_snapshot_index = utils.parse_snapshot_index_for_analysis(
        cfg,
        model_cfg,
        snapshot_index,
        detector_snapshot_index,
    )

    if cropping is None and cfg.get("cropping", False):
        cropping = [cfg["x1"], cfg["x2"], cfg["y1"], cfg["y2"]]

    # Get general project parameters
    multi_animal = cfg["multianimalproject"]
    bodyparts = model_cfg["metadata"]["bodyparts"]
    unique_bodyparts = model_cfg["metadata"]["unique_bodyparts"]
    individuals = model_cfg["metadata"]["individuals"]
    max_num_animals = len(individuals)

    if device is not None:
        model_cfg["device"] = device

    if batch_size is None:
        batch_size = cfg.get("batch_size", 1)

    if not multi_animal:
        save_as_df = True
        if use_shelve:
            print(
                "The ``use_shelve`` parameter cannot be used for single animal "
                "projects. Setting ``use_shelve=False``."
            )
            use_shelve = False

    dynamic = DynamicCropper.build(*dynamic)
    if pose_task != Task.BOTTOM_UP and dynamic is not None:
        print(
            "Turning off dynamic cropping. It should only be used for bottom-up "
            f"pose estimation models, but you are using a top-down model."
        )
        dynamic = None

    snapshot = utils.get_model_snapshots(snapshot_index, train_folder, pose_task)[0]
    print(f"Analyzing videos with {snapshot.path}")
    pose_runner = utils.get_pose_inference_runner(
        model_config=model_cfg,
        snapshot_path=snapshot.path,
        max_individuals=max_num_animals,
        batch_size=batch_size,
        transform=transform,
        dynamic=dynamic,
    )
    detector_runner = None

    detector_path, detector_snapshot = None, None
    if pose_task == Task.TOP_DOWN:
        if detector_snapshot_index is None:
            raise ValueError(
                "Cannot run videos analysis for top-down models without a detector "
                "snapshot! Please specify your desired detector_snapshotindex in your "
                "project's configuration file."
            )

        if detector_batch_size is None:
            detector_batch_size = cfg.get("detector_batch_size", 1)

        detector_snapshot = utils.get_model_snapshots(
            detector_snapshot_index, train_folder, Task.DETECT
        )[0]
        print(f"  -> Using detector {detector_snapshot.path}")
        detector_runner = utils.get_detector_inference_runner(
            model_config=model_cfg,
            snapshot_path=detector_snapshot.path,
            max_individuals=max_num_animals,
            batch_size=detector_batch_size,
        )

    dlc_scorer = utils.get_scorer_name(
        cfg,
        shuffle,
        train_fraction,
        snapshot_uid=utils.get_scorer_uid(snapshot, detector_snapshot),
        modelprefix=modelprefix,
    )

    # Reading video and init variables
    videos: list[Path] = utils.list_videos_in_folder(videos, videotype, shuffle=in_random_order)
    args = [
        (
            config,
            videotype,
            shuffle,
            trainingsetindex,
            save_as_csv,
            destfolder,
            cropping,
            robust_nframes,
            use_shelve,
            auto_track,
            n_tracks,
            animal_names,
            identity_only,
            batch_size,
            overwrite,
            save_as_df,
            cfg,
            train_fraction,
            model_cfg,
            pose_cfg,
            multi_animal,
            bodyparts,
            unique_bodyparts,
            pose_runner,
            detector_runner,
            dlc_scorer,
            video
        )
        for video in videos
    ]
    with Pool(processes=len(videos)) as pool:
        pool.starmap(
            analyze_single_video_dlc,
            args
        )

    print(
        "The videos are analyzed. Now your research can truly start!\n"
        "You can create labeled videos with 'create_labeled_video'.\n"
        "If the tracking is not satisfactory for some videos, consider expanding the "
        "training set. You can use the function 'extract_outlier_frames' to extract a "
        "few representative outlier frames.\n"
    )

    return dlc_scorer


def analyze_single_video_dlc(
    config,
    videotype,
    shuffle,
    trainingsetindex,
    save_as_csv,
    destfolder,
    cropping,
    robust_nframes,
    use_shelve,
    auto_track,
    n_tracks,
    animal_names,
    identity_only,
    batch_size,
    overwrite,
    save_as_df,
    cfg,
    train_fraction,
    model_cfg,
    pose_cfg,
    multi_animal,
    bodyparts,
    unique_bodyparts,
    pose_runner,
    detector_runner,
    dlc_scorer,
    video,
):
    if destfolder is None:
        output_path = video.parent
    else:
        output_path = Path(destfolder)

    output_prefix = video.stem + dlc_scorer
    output_pkl = output_path / f"{output_prefix}_full.pickle"

    video_iterator = VideoIterator(video, cropping=cropping)

    shelf_writer = None
    if use_shelve:
        shelf_writer = shelving.ShelfWriter(
            pose_cfg=pose_cfg,
            filepath=output_pkl,
            num_frames=video_iterator.get_n_frames(robust=robust_nframes),
        )

    if not overwrite and output_pkl.exists():
        print(f"Video {video} already analyzed at {output_pkl}!")
    else:
        runtime = [time.time()]
        predictions = video_inference(
            video=video_iterator,
            pose_runner=pose_runner,
            detector_runner=detector_runner,
            shelf_writer=shelf_writer,
            robust_nframes=robust_nframes,
        )
        runtime.append(time.time())
        metadata = _generate_metadata(
            cfg=cfg,
            pytorch_config=model_cfg,
            dlc_scorer=dlc_scorer,
            train_fraction=train_fraction,
            batch_size=batch_size,
            cropping=cropping,
            runtime=(runtime[0], runtime[1]),
            video=video_iterator,
            robust_nframes=robust_nframes,
        )

        with open(output_path / f"{output_prefix}_meta.pickle", "wb") as f:
            pickle.dump(metadata, f, pickle.HIGHEST_PROTOCOL)

        if use_shelve and save_as_df:
            print("Can't ``save_as_df`` as ``use_shelve=True``. Skipping.")

        if not use_shelve:
            output_data = _generate_output_data(pose_cfg, predictions)
            with open(output_pkl, "wb") as f:
                pickle.dump(output_data, f, pickle.HIGHEST_PROTOCOL)

            if save_as_df:
                create_df_from_prediction(
                    predictions=predictions,
                    multi_animal=multi_animal,
                    model_cfg=model_cfg,
                    dlc_scorer=dlc_scorer,
                    output_path=output_path,
                    output_prefix=output_prefix,
                    save_as_csv=save_as_csv,
                )

        if multi_animal:
            _generate_assemblies_file(
                full_data_path=output_pkl,
                output_path=output_path / f"{output_prefix}_assemblies.pickle",
                num_bodyparts=len(bodyparts),
                num_unique_bodyparts=len(unique_bodyparts),
            )

            if auto_track:
                convert_detections2tracklets(
                    config=config,
                    videos=str(video),
                    videotype=videotype,
                    shuffle=shuffle,
                    trainingsetindex=trainingsetindex,
                    overwrite=False,
                    identity_only=identity_only,
                    destfolder=str(output_path),
                )
                stitch_tracklets(
                    config,
                    [str(video)],
                    videotype,
                    shuffle,
                    trainingsetindex,
                    n_tracks=n_tracks,
                    animal_names=animal_names,
                    destfolder=str(output_path),
                    save_as_csv=save_as_csv,
                )
