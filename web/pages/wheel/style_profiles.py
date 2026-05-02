from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StyleProfile:
    key: str
    label: str
    dte: int
    ivr_min: float
    rsi_max: float
    put_otm: float
    call_otm: float
    put_tp: float
    call_tp: float
    put_sl: float | None
    confirm_days: int = 0
    cooldown_days: int = 0
    roll_preferred: bool = False
    roll_stop_threshold: float | None = None
    cc_min_cost_basis: bool = False
    cc_pause_below_cost_ratio: float | None = None
    entry_cycle_days: int = 7


STYLE_PROFILES: dict[str, StyleProfile] = {
    "aggressive": StyleProfile(
        key="aggressive",
        label="激进",
        dte=7,
        ivr_min=20.0,
        rsi_max=65.0,
        put_otm=0.06,
        call_otm=0.02,
        put_tp=0.50,
        call_tp=0.80,
        put_sl=None,
        entry_cycle_days=7,
    ),
    "neutral": StyleProfile(
        key="neutral",
        label="中性",
        dte=21,
        ivr_min=35.0,
        rsi_max=50.0,
        put_otm=0.09,
        call_otm=0.06,
        put_tp=0.50,
        call_tp=0.50,
        put_sl=2.0,  # loss >= 200% premium
        entry_cycle_days=21,
    ),
    "conservative": StyleProfile(
        key="conservative",
        label="保守",
        dte=45,
        ivr_min=50.0,
        rsi_max=40.0,
        put_otm=0.12,
        call_otm=0.0,  # near cost basis
        put_tp=0.50,
        call_tp=0.50,
        put_sl=1.5,  # 150%
        confirm_days=1,
        cooldown_days=5,
        roll_preferred=True,
        roll_stop_threshold=1.0,  # start considering roll at 100% loss
        cc_min_cost_basis=True,
        cc_pause_below_cost_ratio=0.90,
        entry_cycle_days=30,
    ),
}

