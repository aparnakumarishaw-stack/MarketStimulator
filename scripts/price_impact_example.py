"""Generate and save a price-impact curve using a sample engine setup."""
from __future__ import annotations
import os
from simulate import plot_price_impact_curve
from market_engine import MarketEngine
from bots import MarketMaker


def main(savepath: str = "price_impact_example.png") -> str:
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    # Add a market maker so there is ongoing liquidity
    mm = MarketMaker(spread=1.0, size=1.0, jitter=0.0)
    engine.register_bot(mm)

    # Pre-warm a few ticks so MM posts some liquidity
    for _ in range(3):
        engine.step()

    plot_price_impact_curve(engine, savepath=savepath)
    saved = os.path.abspath(savepath)
    print(f"Saved price-impact example to: {saved}")
    return saved


if __name__ == "__main__":
    main()
