from typing import List

from pydantic import BaseModel


class SkellyClickerUIState(BaseModel):
    saved_path: str | None = None
    is_playing: bool = False
    project_path: str | None = None
    video_files: List[str] | None = None
    auto_save: bool = False
    show_help: bool = False
