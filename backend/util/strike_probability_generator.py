import pandas as pd
import numpy as np
import math
from typing import Iterable, Tuple, Union

# ---------------------------------------------------------------------
# 1. CORE MODEL FUNCTION
# ---------------------------------------------------------------------
def touch_probability(delta: float, t: float,
                      fingerprint: Tuple[float, float, float]) -> float:
    """Return probability of touching given % distance within t minutes."""
    k, alpha, beta = fingerprint
    return 1.0 - math.exp(-k * (delta ** alpha) * (t ** beta))

# ---------------------------------------------------------------------
# 2. TABLE-BUILDER
# ---------------------------------------------------------------------
def build_strike_table(
    strikes: Iterable[Union[int, float]],
    current_price: float,
    ttc_minutes: float,
    fingerprint: Tuple[float, float, float],
    pct_decimals: int = 3,
) -> pd.DataFrame:
    """
    Build a DataFrame of touch probabilities for each strike.
    """
    rows = []
    for strike in strikes:
        buffer_val = abs(strike - current_price)
        delta = buffer_val / current_price
        prob = touch_probability(delta, ttc_minutes, fingerprint)
        rows.append(
            {
                "Strike": strike,
                "Buffer ($)": buffer_val,
                "% Distance": round(delta * 100, pct_decimals),
                "Prob Touch (%)": round(prob * 100, 2),
            }
        )

    df = pd.DataFrame(rows).sort_values("Strike").reset_index(drop=True)
    return df

# ---------------------------------------------------------------------
# 3. EXAMPLE USAGE  (replace with real-time inputs in production)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    # >>>>>> REPLACE the next three lines with live inputs <<<<<<
    FINGERPRINT = (2.14e-7, -1.95, 0.98)     # (k, alpha, beta) for BTC
    CURRENT_PRICE = 109_136                  # live spot price
    TTC_MINUTES   = 12.5                     # minutes to close
    # ----------------------------------------------------------

    # Define strikes (could pull from market data, DB, etc.)
    strike_list = [
        CURRENT_PRICE - 636,  # 3 below
        CURRENT_PRICE - 386,
        CURRENT_PRICE - 136,
        CURRENT_PRICE + 114,  # 3 above
        CURRENT_PRICE + 364,
        CURRENT_PRICE + 614,
    ]

    table = build_strike_table(
        strikes=strike_list,
        current_price=CURRENT_PRICE,
        ttc_minutes=TTC_MINUTES,
        fingerprint=FINGERPRINT,
    )

    # Display or return to caller
    print(table.to_string(index=False)) 