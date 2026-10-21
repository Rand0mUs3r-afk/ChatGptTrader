
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Market data
    benchmark: str = "SPY"
    period: str = "5y"
    interval: str = "1d"
    minimum_history: int = 220

    # Tradability filters
    minimum_price: float = 5.0
    minimum_average_dollar_volume: float = 10_000_000

    # Indicators
    ema_period: int = 20
    sma_period: int = 50
    long_sma_period: int = 200
    atr_period: int = 14
    rsi_period: int = 14
    volume_period: int = 20
    breakout_period: int = 20
    relative_strength_period: int = 20

    # Entry filters
    minimum_relative_volume: float = 1.5
    maximum_extension_atr: float = 2.0
    pullback_distance_atr: float = 0.5
    require_benchmark_uptrend: bool = True

    # Trade plan
    target_r_multiple: float = 2.0
    maximum_holding_days: int = 5
    minimum_reward_risk: float = 1.5

    # Portfolio assumptions for position sizing
    account_equity: float = 25_000.0
    risk_fraction: float = 0.005
    maximum_position_fraction: float = 0.20
    maximum_positions: int = 5

    # Candidate ranking
    minimum_signal_score: float = 65.0

    # Research execution assumptions
    commission_per_share: float = 0.0
    slippage_bps: float = 5.0


DEFAULT_SETTINGS = Settings()
