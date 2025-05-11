import logging
import multiprocessing

from skellyclicker.models.skellyclicker_app_state_model import SkellyClickerAppState

logger = logging.getLogger(__name__)

SKELLYCLICKER_APP_STATE: SkellyClickerAppState | None = None

def create_skellyclicker_app_state(global_kill_flag: multiprocessing.Value) -> SkellyClickerAppState:
    global SKELLYCLICKER_APP_STATE
    if SKELLYCLICKER_APP_STATE is None:
        SKELLYCLICKER_APP_STATE = SkellyClickerAppState.create(global_kill_flag=global_kill_flag)
    else:
        raise ValueError("SkellyBotAnalysis already exists!")
    return SKELLYCLICKER_APP_STATE


def get_skellyclicker_app_state() -> SkellyClickerAppState:
    global SKELLYCLICKER_APP_STATE
    if SKELLYCLICKER_APP_STATE is None:
        raise ValueError("SkellyBotAnalysis does not exist!")
    return SKELLYCLICKER_APP_STATE
