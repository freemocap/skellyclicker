import cv2
import numpy as np
from pydantic import BaseModel

from skellyclicker.core.video_handler.video_models import ClickData


def draw_doubled_text(image: np.ndarray,
                      text: str,
                      x: int,
                      y: int,
                      font_scale: float,
                      color: tuple[int, ...],
                      thickness: int,
                        line_spacing: int = 30,
                        ) -> None:

    for line in text.split("\n"):
        if line:
            cv2.putText(image, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness * 3)
            cv2.putText(image, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, color, thickness)
        y += line_spacing


SHORT_HELP_TEXT = "H for Help, \nEsc to Quit"

FULL_HELP_TEXT = (
    "Click on the video to add a point.\n"
    "Use 'a' and 'd' to navigate through frames.\n"
    "Press 'f' and 'g' to jump to navigate through labeled frames.\n"
    "Use 'w' and 's' to change the active point.\n"
    "Use 'e' to zoom in and 'q' to zoom out.\n"
    "Use 'r' to reset the zoom.\n"
    "Use 'j', 'i', 'k', 'l' to pan.\n"
    "Press 'u' to clear the data for active point\n"
    "for the current frame.\n"
    "Press 'c' to toggle auto next point.\n"
    "Press 'm' to toggle machine labels visibility.\n"
    "Press 'v' to copy machine labels to labelled data.\n"
    "Press 'n' to toggle point name visibility.\n"
    "Press 'h' to toggle help text.\n"
    "Press 'Esc' to quit.\n"
    "You will be prompted to save the data in the terminal."
)


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


class ImageAnnotatorConfig(BaseModel):
    marker_type: int = cv2.MARKER_DIAMOND
    marker_size: int = 15
    marker_thickness: int = 1

    text_color: tuple[int, int, int] = (215, 115, 40)
    text_size: float = 1
    text_thickness: int = 2
    text_font: int = cv2.FONT_HERSHEY_SIMPLEX

    show_help: bool = False
    show_clicks: bool = True
    show_names: bool = True
    tracked_points: list[str] = []


class ImageAnnotator(BaseModel):
    config: ImageAnnotatorConfig = ImageAnnotatorConfig()

    def annotate_image_grid(self,
                            image: np.ndarray,
                            active_point: str,
                            frame_number: int) -> np.ndarray:
        if self.config.show_help:
            help_text = FULL_HELP_TEXT
        else:
            help_text = SHORT_HELP_TEXT
        draw_doubled_text(image=image,
                          text=f"Frame Number: {frame_number}\n {active_point}",
                          x=(image.shape[1] // 10) * 8,
                          y=(image.shape[0] // 10) * 9,
                          font_scale=self.config.text_size,
                          color=(255,0,255),
                          thickness=self.config.text_thickness)

        draw_doubled_text(image=image,
                          text=help_text,
                          x=10,
                          y=(image.shape[0] // 10) * 3,
                          font_scale=self.config.text_size,
                          color=self.config.text_color,
                          thickness=self.config.text_thickness)
        return image

    def annotate_single_image(
            self,
            image: np.ndarray,
            active_point: str | None = None,
            click_data: dict[str, ClickData] | None = None,
    ) -> np.ndarray:
        image_height, image_width = image.shape[:2]
        text_offset = int(image_height * 0.05)

        if click_data is None:
            click_data = {}
        # Copy the original image for annotation
        annotated_image = image.copy()
        marker_colors = get_colors(self.config.tracked_points)
        # Draw a marker for each click
        for point_name, click in click_data.items():
            marker_color = marker_colors.get(point_name, (255, 0, 255))
            cv2.drawMarker(
                annotated_image,
                position=(click.x, click.y),
                color=(1, 1, 1),
                markerType=self.config.marker_type,
                markerSize=int(self.config.marker_size * 1.3),
                thickness=int(self.config.marker_thickness * 1.3),
            )
            cv2.drawMarker(
                annotated_image,
                position=(click.x, click.y),
                color=marker_color,
                markerType=self.config.marker_type,
                markerSize=self.config.marker_size,
                thickness=self.config.marker_thickness,
            )
            if self.config.show_names:
                draw_doubled_text(image=annotated_image,
                                  text=point_name,
                                  x=click.x + self.config.marker_size,
                                  y=click.y - self.config.marker_size,
                                  font_scale=self.config.text_size * .7,
                                  color=marker_color,
                                  thickness=1,
                                  )

        if self.config.show_clicks:
            # List the markers on the image, with a check or x based on if they are labeled
            label_string = ""
            for tracked_point in self.config.tracked_points:
                if tracked_point in click_data:
                    label_string += f"{tracked_point}: {click_data[tracked_point].x}, {click_data[tracked_point].y} "
                else:
                    label_string += f"{tracked_point}: (?, ?) "

                if active_point and tracked_point == active_point:
                    label_string += " <-(active)"
                label_string += "\n"

            draw_doubled_text(image=annotated_image,
                            text=label_string,
                            x=text_offset,
                            y=text_offset,
                            font_scale=self.config.text_size*.75,
                            color= (255, 150, 55),
                            thickness=self.config.text_thickness,
                            line_spacing=30,
                            )
        return annotated_image
