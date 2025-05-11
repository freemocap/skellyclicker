from pathlib import Path

SKELLYCLICKER_LOGO_PNG = str(Path(__file__).parent / "skellyclicker-logo.png")
SKELLYCLICKER_LOGO_ICO = str(Path(__file__).parent / "skellyclicker-logo.ico")

if not Path(SKELLYCLICKER_LOGO_PNG).exists():
    raise RuntimeError(f"SkellyClicker logo not found at{str(SKELLYCLICKER_LOGO_PNG)}")

if not Path(SKELLYCLICKER_LOGO_ICO).exists():
    raise RuntimeError(f"SkellyClicker logo not found at{str(SKELLYCLICKER_LOGO_ICO)}")
