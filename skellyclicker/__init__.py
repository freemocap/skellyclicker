
__url__ = "https://github.com/freemocap/skellyclicker"
__author__ = """Skelly FreeMoCap    """
__email__ = "info@freemocap.org"
__version__ = "v0.1.0"
__description__ = f"For clicking on stuff ({__url__})"

__package_name__ = "skellyclicker"
__repo_url__ = f"https://github.com/freemocap/{__package_name__}/"
__repo_issues_url__ = f"{__repo_url__}issues"

from skellyclicker.system.logging_configuration.configure_logging import configure_logging
from skellyclicker.system.logging_configuration.logger_builder import LogLevels

configure_logging(LogLevels.DEBUG)
