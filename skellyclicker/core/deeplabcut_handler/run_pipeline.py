import logging
from pathlib import Path
from datetime import datetime
import deeplabcut
from dlc_utils.create_dlc_config import create_new_project
from dlc_utils.create_dlc_project_data import fill_in_labelled_data_folder
from dlc_utils.project_config import ProjectConfig, DataConfig, TrainingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_dlc_pipeline(
    project: ProjectConfig,
    data: DataConfig,
    training: TrainingConfig
):

    timestamp = datetime.now().strftime("%Y%m%d") 
    full_project_name = f"{project.name}_{project.experimenter}_{timestamp}"
    project_path = project.working_directory/full_project_name

    logger.info(f"Starting DLC pipeline for project: {full_project_name}")
    
    # Step 1: Create project
    logger.info("Creating project structure...")
    config_path = create_new_project(
        project=full_project_name,
        experimenter=project.experimenter,
        working_directory=project.working_directory,
        bodyparts=project.bodyparts,
        skeleton=project.skeleton
    )
    
    
    # Step 2: Fill in labeled data
    logger.info("Processing labeled frames...")
    labeled_frames = fill_in_labelled_data_folder(
        path_to_videos_for_training=data.folder_of_videos,
        path_to_dlc_project_folder=project_path,
        path_to_image_labels_csv=data.labels_csv_path,
        scorer_name= project.experimenter
    )
    
    # Step 3: Create training dataset
    logger.info("Creating training dataset...")
    deeplabcut.create_training_dataset(
        config=config_path,
    )
    
    # Step 4: Train network
    logger.info("Training network...")
    deeplabcut.train_network(
        config=config_path,
        epochs=training.epochs,
        save_epochs=training.save_epochs,
        batch_size=training.batch_size
    )

    logger.info(f"Saving config values to {config_path}")
    training.update_config_yaml(config_path)
    data.update_config_yaml(config_path)
    
    logger.info(f"Pipeline completed for project: {full_project_name}")
    logger.info(f"Project path: {project_path}")

    
    return {
        "project_name": full_project_name,
        "config_path": config_path,
        "project_path": str(project_path),
        "labeled_frames": labeled_frames
    }

if __name__ == "__main__":
    #(using the DLC 3.0 installation, following these instructions https://github.com/DeepLabCut/DeepLabCut/pull/2613)

    from dlc_utils.project_config import ProjectConfig, DataConfig, TrainingConfig

    project_config = ProjectConfig(
        name = "sample_data_test2",
        experimenter= "user", #can probably look into removing the experimenter/scorer entirely
        working_directory= Path("/Users/philipqueen/DLCtest"), #optional, defaults to CWD otherwise
        bodyparts=[
            'right_eye_inner', 'left_eye_inner', 'nose',
        ],
        skeleton=[
            ['left_eye_inner', 'nose'],
            ['nose', 'right_eye_inner'],
        ], #skeleton is optional 
    )
    
    data_config = DataConfig(
        folder_of_videos= Path("/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/synchronized_videos/"),
        labels_csv_path= Path("/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/skellyclicker_data/2025-04-03_17-25-38_skellyclicker_output.csv")
    )

    training_config = TrainingConfig(
        model_type = "resnet_50",
        epochs = 200, #this is the new equivalent of 'maxiters' for PyTorch (200 is their default)
        save_epochs= 50, #this is the new equivalent of 'save_iters' for PyTorch
        batch_size = 2 #this seems to be similar to batch/multi processing (higher number = faster processing if your gpu can handle it?)
    )

    # Run the pipeline
    project_info = run_dlc_pipeline(
        project=project_config,
        data=data_config,
        training=training_config
    )
    
    print(f"Project created: {project_info['project_name']}")            

    ##NOTE- the 'training-dataset' folder is tagged with the 'date' from the config yaml, as per DLC. This is dumb, we should change it - but that would require also pulling out the 'create_training_dataset' function from deeplabcut
