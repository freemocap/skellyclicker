from pathlib import Path
import pandas as pd
import cv2

def load_deeplabcut_labels(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path, header=[1,2], skiprows=0)

def view_labelled_data(csv_path: Path):
    project_folder = csv_path.parent.parent
    df = load_deeplabcut_labels(csv_path)
    print(df.head(5))
    
    bodyparts = df.columns.get_level_values(0).unique()
    for bodypart in bodyparts:
        print(f"Bodypart: {bodypart}")

    for index, row in df.iterrows():
        path_stem = ""
        image_path = project_folder / path_stem
        image = cv2.imread(str(image_path))

        for bodypart in bodyparts:
            x = row[bodypart]["x"]
            y = row[bodypart]["y"]
            cv2.circle(image, (int(x), int(y)), 5, (0, 0, 255), -1)

        cv2.imshow(f"{path_stem}", image)
        cv2.waitKey(0)


if __name__ == "__main__":
    csv_path = Path("/home/scholl-lab/ferret_recordings/session_2025-07-11_ferret_757_EyeCamera_P43_E15__1/clips/0m_37s-1m_37s/mocap_data/dlc_output/skellyclicker_machine_labels_iteration_1.csv")
    view_labelled_data(csv_path)