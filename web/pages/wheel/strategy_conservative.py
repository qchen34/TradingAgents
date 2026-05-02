from web.pages.wheel.style_profiles import STYLE_PROFILES
from web.pages.wheel.wheel_shared import run_style_tab


def render_tab(state_prefix: str = "wheel", default_underlying: str = "TQQQ", default_signal: str = "QQQ") -> None:
    run_style_tab(
        style=STYLE_PROFILES["conservative"],
        state_prefix=state_prefix,
        default_underlying=default_underlying,
        default_signal=default_signal,
    )

