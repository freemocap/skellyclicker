import logging

from pydantic import BaseModel

from skellyclicker.core.deeplabcut_handler.create_deeplabcut.create_deeplabcut_config import \
    create_new_deeplabcut_project
from skellyclicker.core.deeplabcut_handler.create_deeplabcut.deelabcut_project_config import \
    SimpleDeeplabcutProjectConfig

logger = logging.getLogger(__name__)


class PointConnection(BaseModel):
    parent: str
    child: str

    @classmethod
    def from_tuple(cls, points: tuple[str, str]):
        return cls(parent=points[0],
                   child=points[1])

    @property
    def as_tuple(self) -> tuple[str, str]:
        return self.parent, self.child

    @property
    def as_list(self) -> list[str]:
        return list(self.as_tuple)


class DeeplabcutHandler(BaseModel):
    project_name: str
    project_config_path: str
    tracked_point_names: list[str]
    connections: list[PointConnection]

    @classmethod
    def create_deeplabcut_project(cls,
                                  project_name: str,
                                  project_parent_directory: str,
                                  tracked_point_names: list[str],
                                  connections: list[PointConnection]):
        logger.info(f"Starting DLC pipeline for project: {project_name}")

        logger.info("Creating deeplabcut project structure...")
        return cls(project_name=project_name,
                   connections=connections,
                   tracked_point_names=tracked_point_names,
                   project_config_path=create_new_deeplabcut_project(project_name=project_name,
                                                                     project_parent_directory=project_parent_directory,
                                                                     bodyparts=tracked_point_names,
                                                                     skeleton=[connection.as_list for connection in
                                                                               connections]
                                                                     )
                   )

    def update_project_data(self):
        pass

    def train_model(self):
        pass
