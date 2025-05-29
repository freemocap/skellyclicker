import logging
import multiprocessing
import time
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from skellyclicker.api.server.server_singleton import create_server_manager
from skellyclicker.system.logging_configuration.configure_logging import configure_logging
from skellyclicker.system.logging_configuration.logger_builder import LogLevels

logger = logging.getLogger(__name__)
configure_logging(LogLevels.TRACE)


def run_skellyclicker_server(global_kill_flag: multiprocessing.Value):
    server_manager = create_server_manager(global_kill_flag=global_kill_flag)
    server_manager.start_server()
    while server_manager.is_running: #TODO: This doesn't shut down gracefully
        time.sleep(1)
        if global_kill_flag.value:
            server_manager.shutdown_server()
            break

    logger.info("Server main process ended")


if __name__ == "__main__":

    outer_global_kill_flag = multiprocessing.Value("b", False)
    try:
        run_skellyclicker_server(outer_global_kill_flag)
        outer_global_kill_flag.value = True
    except Exception as e:
        logger.error(f"Server main process ended with error: {e}")
        raise
    finally:
        outer_global_kill_flag.value = True
    print("Done!")