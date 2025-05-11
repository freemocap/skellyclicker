# skellyclicker

For labelling and training data through DeepLabCut.

## Installation

1. Clone the repository

2. Change the directory to the cloned repository

    - `cd skellyclicker`

3. Create a new conda environment from the environment yaml

    - `conda env create -f skellyclicker_env.yaml`

## How To Use

1. Activate the environment.

2. Open the GUI.
    - `python skellyclicker/__main__.py`

3. Start a new session or load an existing one.
    - When loading a session, look for the `.json` file you saved on a previous session.

4. Label the videos by clicking `load videos` on the first iteration, or `open videos` on subsequent iterations
    - Make sure you save the videos after labelling
    
5. Create a DeepLabCut project or load an existing project if you haven't yet

6. Train the model with the `Train Network` button

7. Click `Analyze Videos` to run the model on videos. If you run the model on the training videos, this will allow you to see the models output in the next round of labelling. 

8. Repeat steps 4-7 until the model performs sufficiently well.
