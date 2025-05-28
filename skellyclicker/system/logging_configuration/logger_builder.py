import logging
from logging.config import dictConfig
from multiprocessing import Queue
from typing import Optional

from .log_format_string import LOG_FORMAT_STRING
from .log_levels import LogLevels
from ..files_and_folder_names import get_log_file_path

MAX_DELTA_T_LEN = 10


class LoggerBuilder:

    def __init__(self,
                 level: LogLevels ,
                 queue: Optional[Queue] = None):
        self.level = level
        self.queue = queue
        dictConfig({"version": 1, "disable_existing_loggers": False})

    def _configure_root_logger(self):
        root = logging.getLogger()
        root.setLevel(self.level.value)

        # Clear existing handlers
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        # Add new handlers
        root.addHandler(self._build_file_handler())

    def _build_file_handler(self):
        handler = logging.FileHandler(get_log_file_path(), encoding="utf-8")
        handler.setFormatter(logging.Formatter(LOG_FORMAT_STRING))
        # handler.addFilter(DeltaTimeFilter())
        handler.setLevel(LogLevels.TRACE.value)
        return handler

    def configure(self):
        if len(logging.getLogger().handlers) == 0:
            self._configure_root_logger()
