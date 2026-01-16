import numpy as np

from pathlib import Path
from pydantic import BaseModel

from skellyforge.post_processing.interpolation.apply_interpolation import (
    interpolate_trajectory,
)
from skellyforge.post_processing.interpolation.interpolation_config import (
    InterpolationConfig,
    InterpolationMethod,
)
from skellyforge.post_processing.filters.apply_filter import filter_trajectory
from skellyforge.post_processing.filters.filter_config import FilterConfig, FilterMethod
from skellyforge.skellymodels.managers.human import Human, Animal
from skellyforge.skellymodels.models.tracking_model_info import ModelInfo
from skellyforge.triangulation.triangulate import triangulate_dict, TriangulationConfig
from skellyforge.triangulation.load_camera_group import load_camera_group_from_toml

from skellyclicker.scripts.processing.compile_dlc_csvs import compile_dlc_csvs


class TrackingConfig(
    BaseModel
):  # this seems like something that could be integrated or made earlier in the pipeline, so just leaving it here for now
    tracker: str
    name: str = (
        "animal"  # the existence of the name is something I've questioned for a bit - but I do think it could be useful when we get to multi-person for appending to file names (human_one vs. two vs. user input etc.), which is why I've held onto it
    )
    model_info: ModelInfo


def loaded_dlc_pipeline(
    dlc_output_folder: Path,
    confidence_threshold: float,
    camera_calibration_toml_path: Path,
    output_folder: Path,
    interp_config: InterpolationConfig,
    filter_config: FilterConfig,
    tracking_config: TrackingConfig,
    triangulation_config: TriangulationConfig,
):
    camera_group = load_camera_group_from_toml(
        camera_calibration_data_toml_path=camera_calibration_toml_path
    )

    dlc_data = compile_dlc_csvs(
        path_to_folder_with_dlc_csvs=dlc_output_folder,
        confidence_threshold=confidence_threshold,
    )

    raw_trajectory = triangulate_dict(
        data_dict=dlc_data,
        camera_group=camera_group,
        config=triangulation_config,
    )

    interpolated_trajectory = interpolate_trajectory(raw_trajectory, interp_config)

    filtered_trajectory = filter_trajectory(interpolated_trajectory, filter_config)

    skellymodel: Animal = (
        Animal.from_tracked_points_numpy_array(  # perhaps need to rethink the 'Animal'/'Human' distinction - there might be a more elegant solution?
            name=tracking_config.name,
            model_info=tracking_config.model_info,
            tracked_points_numpy_array=filtered_trajectory.triangulated_data,
        )
    )

    skellymodel.save_out_numpy_data(path_to_output_folder=output_folder)
    skellymodel.save_out_csv_data(path_to_output_folder=output_folder)
    skellymodel.save_out_all_data_csv(path_to_output_folder=output_folder, prefix=tracking_config.model_info.name)
    skellymodel.save_out_all_data_parquet(path_to_output_folder=output_folder, prefix=tracking_config.model_info.name)
    skellymodel.save_out_all_xyz_numpy_data(path_to_output_folder=output_folder)


if __name__ == "__main__":
    path_to_dlc_csvs = Path(
        "D:\2023-06-07_TF01\1.0_recordings\four_camera\sesh_2023-06-07_12_06_15_TF01_flexion_neutral_trial_1\output_data\raw_data\dlc_3dData_numFrames_numTrackedPoints_spatialXYZ.npy"
    )
    path_to_calibration_toml = Path(
        "/Users/philipqueen/session_2025-07-11_ferret_757_EyeCamera_P43_E15__1/calibration/session_2025_07_11_calibration_camera_calibration.toml"
    )
    interp_config = InterpolationConfig(method=InterpolationMethod.linear)

    filter_config = FilterConfig(
        method=FilterMethod.butter_low_pass, cutoff=6.0, sampling_rate=30.0, order=4
    )

    path_to_model_yaml = Path(
        "skellyclicker/scripts/processing/ferret_eye_cam.yaml"
    )
    model_info = ModelInfo.from_config_path(path_to_model_yaml)

    tracking_config = TrackingConfig(
        tracker="head", name=model_info.name, model_info=model_info
    )

    triangulation_config = TriangulationConfig(use_ransac=False)

    loaded_dlc_pipeline(
        dlc_output_folder=path_to_dlc_csvs,
        confidence_threshold=0.5,
        camera_calibration_toml_path=path_to_calibration_toml,
        output_folder=path_to_dlc_csvs.parent,
        interp_config=interp_config,
        filter_config=filter_config,
        tracking_config=tracking_config,
        triangulation_config=triangulation_config,
    )
