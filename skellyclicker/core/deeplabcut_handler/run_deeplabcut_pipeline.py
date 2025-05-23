import logging
from pathlib import Path
from datetime import datetime
import deeplabcut

from skellyclicker.core.deeplabcut_handler.create_deeplabcut.create_deeplabcut_config import create_new_deeplabcut_project
from skellyclicker.core.deeplabcut_handler.create_deeplabcut.create_deeplabcut_project_data import \
    fill_in_labelled_data_folder
from skellyclicker.core.deeplabcut_handler.create_deeplabcut.deelabcut_project_config import SimpleDeeplabcutProjectConfig, SkellyClickerDataConfig, \
    TrainingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_dlc_pipeline(
    project: SimpleDeeplabcutProjectConfig,
    data: SkellyClickerDataConfig,
    training: TrainingConfig
):

    timestamp = datetime.now().strftime("%Y%m%d") 
    full_project_name = f"{project.name}_{project.experimenter}_{timestamp}"
    project_path = Path(project.config_yaml_path) / full_project_name

    logger.info(f"Starting DLC pipeline for project: {full_project_name}")
    
    # Step 1: Create project
    logger.info("Creating deeplabcut project structure...")
    config_path = create_new_deeplabcut_project(
        project_name=full_project_name,
        experimenter=project.experimenter,
        project_parent_directory=project.config_yaml_path,
        bodyparts=project.bodyparts,
        skeleton=project.skeleton
    )
    
    
    # Step 2: Fill in labeled data
    logger.info("Processing labeled frames...")
    labeled_frames = fill_in_labelled_data_folder(
        path_to_videos_for_training=data.folder_of_videos,
        path_to_dlc_project_folder=project_path,
        path_to_image_labels_csv=data.click_data_csv_path,
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


    project_config = SimpleDeeplabcutProjectConfig(
        name = "sample_data_test2",
        experimenter= "user", #can probably look into removing the experimenter/scorer entirely
        config_yaml_path="/Users/philipqueen/DLCtest", #optional, defaults to CWD otherwise
        bodyparts=[
            'right_eye_inner', 'left_eye_inner', 'nose',
        ],
        skeleton=[
            ['left_eye_inner', 'nose'],
            ['nose', 'right_eye_inner'],
        ], #skeleton is optional 
    )
    
    data_config = SkellyClickerDataConfig(
        folder_of_videos= Path("/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/synchronized_videos/"),
        click_data_csv_path= Path("/Users/philipqueen/freemocap_data/recording_sessions/freemocap_test_data/skellyclicker_data/2025-04-03_17-25-38_skellyclicker_output.csv")
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
