from pathlib import Path
import numpy as np
import pandas as pd
import cv2

def load_deeplabcut_labels(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path, header=[1,2], skiprows=0)

def hsv_to_rgb(hsv: np.ndarray) -> np.ndarray:
    """Convert HSV color to RGB."""
    h, s, v = hsv
    hi = int(h * 6.) % 6
    f = h * 6. - int(h * 6.)
    p = v * (1. - s)
    q = v * (1. - f * s)
    t = v * (1. - (1. - f) * s)

    if hi == 0:
        return np.array([v, t, p])
    elif hi == 1:
        return np.array([q, v, p])
    elif hi == 2:
        return np.array([p, v, t])
    elif hi == 3:
        return np.array([p, q, v])
    elif hi == 4:
        return np.array([t, p, v])
    else:
        return np.array([v, p, q])

def get_colors(keys: list[str]) -> dict[str, tuple[int, ...]]:
    np.random.seed(42)

    hues = np.linspace(0, 1, len(keys), endpoint=False)

    # Convert HSV to RGB
    rgb_values = []
    for hue in hues:
        hsv = np.array([hue, 1, 0.95])
        rgb = hsv_to_rgb(hsv)
        rgb_values.append(tuple(map(int, rgb * 255)))

    colors = {}
    for tracked_point, color in zip(keys, rgb_values):
        colors[tracked_point] = color

    return colors

def view_labelled_data(csv_path: Path):
    project_folder = csv_path.parent.parent.parent
    df = load_deeplabcut_labels(csv_path)
    print(df.head(5))
    
    bodyparts = df.columns.get_level_values(0).unique()


    colors = get_colors(bodyparts[1:])

    # for bodypart in bodyparts[1:]:
    #     print(f"Bodypart: {bodypart} Color: {colors[bodypart]}")

    for index, row in df.iterrows():
        path_stem = row["bodyparts", "coords"]
        image_path = project_folder / path_stem
        image = cv2.imread(str(image_path))

        cv2.putText(image, path_stem.split("/")[-1], (2, 40), cv2.FONT_HERSHEY_SIMPLEX, 2, (0,0,255), 1)

        for bodypart in bodyparts[1:]:
            x = row[bodypart, "x"]
            y = row[bodypart, "y"]
            try:
                x = int(x)
                y = int(y)
            except ValueError as e:
                print(f"got exception {e}")
                print(f"Check data for image {path_stem} for null values")
                continue

            marker_color = colors.get(bodypart, (255, 0, 255))
            cv2.drawMarker(
                image,
                position=(x, y),
                color=(1, 1, 1),
                markerType=cv2.MARKER_DIAMOND,
                markerSize=20,
                thickness=2,
            )
            cv2.drawMarker(
                image,
                position=(x, y),
                color=marker_color,
                markerType=cv2.MARKER_DIAMOND,
                markerSize=15,
                thickness=1,
            )
            cv2.putText(
                image,
                bodypart,
                (x+15, y-15),
                cv2.FONT_HERSHEY_PLAIN,
                1,
                marker_color,
                1
            )

        print(f"showing {path_stem}")
        cv2.imshow("Labelled Data", image)
        key = cv2.waitKey(0)
        if key == ord('0'):
            break
        elif key == ord('q'):
            continue

    cv2.destroyAllWindows()


if __name__ == "__main__":
    data_folder_path = Path(
        "/home/scholl-lab/deeplabcut_data/eye_model_v3/labeled-data/session_2025-10-11_ferret_420_E02_eye0"
    )
    csv_path = data_folder_path / "CollectedData_human.csv"
    view_labelled_data(csv_path)