"""simulate.py — run a simple MarketStimulator experiment and save diagnostics.

This script runs a short simulation (default 100 ticks) and saves a plot showing the
latent true price and executed trades.
"""
from __future__ import annotations
import os
import numpy as np
import matplotlib
# Use Agg backend for headless environments (tests/CI)
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from market_engine import MarketEngine
from bots import MarketMaker

OUTPUT_PATH = "market_simulation.png"


def run_simulation(ticks: int = 100, seed: int | None = 1, savepath: str = OUTPUT_PATH) -> str:
    rng = np.random.default_rng(seed)

    engine = MarketEngine(init_price=100.0, vol=0.5, rng=rng)

    # Register a couple of market makers to create trades
    mm1 = MarketMaker(spread=1.0, size=1.0, jitter=0.05, rng=rng)
    mm2 = MarketMaker(spread=1.2, size=1.0, jitter=0.05, rng=rng)
    engine.register_bot(mm1)
    engine.register_bot(mm2)

    for _ in range(ticks):
        engine.step()

    # Gather trade prices and ticks
    trade_prices = [t["price"] for t in engine.trade_history]
    trade_ticks = [t["tick"] for t in engine.trade_history]

    # Plotting
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(engine.true_history, label="True Price", lw=1.5)
    if trade_prices:
        ax.scatter(trade_ticks, trade_prices, color="red", s=10, alpha=0.7, label="Trades")

    ax.set_xlabel("Tick")
    ax.set_ylabel("Price")
    ax.set_title(f"Market Simulation — {ticks} ticks")
    ax.legend()
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(savepath)
    plt.close(fig)

    print(f"Saved simulation plot to: {os.path.abspath(savepath)}")
    return os.path.abspath(savepath)


def plot_depth(engine: 'MarketEngine', savepath: str = "market_depth.png", *, hover: bool = True, interactive: bool = False, interactive_path: str | None = None) -> str:
    """Plot a cumulative depth chart (asks & bids) from the engine's order book.

    Features:
    - Steps plot for asks (sell) and bids (buy)
    - Shaded area between best bid and best ask to visualize the spread
    - Optional hover (matplotlib + mplcursors) to show price & cumulative size
    - Optional interactive HTML output using Plotly when `interactive=True` (saves to `interactive_path` or adds `.html` next to `savepath`)
    """
    try:
        import seaborn as sns  # optional styling
        sns.set_style("whitegrid")
    except Exception:
        sns = None

    df = engine.get_cumulative_depth()

    bids = df[df["side"] == "buy"].sort_values("price", ascending=True)
    asks = df[df["side"] == "sell"].sort_values("price", ascending=True)

    fig, ax = plt.subplots(figsize=(10, 5))

    if not asks.empty:
        ax.step(asks["price"], asks["cum_size"], where="post", label="Asks (sell)", color="red")
    if not bids.empty:
        ax.step(bids["price"], bids["cum_size"], where="post", label="Bids (buy)", color="green")

    # Shade spread between best bid and best ask (if both exist)
    best_bid = bids["price"].max() if not bids.empty else None
    best_ask = asks["price"].min() if not asks.empty else None
    if best_bid is not None and best_ask is not None and best_bid < best_ask:
        ax.axvspan(best_bid, best_ask, color="gray", alpha=0.15)
        ax.text(0.5 * (best_bid + best_ask), ax.get_ylim()[1] * 0.95, f"Spread: {best_ask - best_bid:.4f}",
                ha="center", va="top", fontsize=9, color="black", bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"))

    ax.set_xlabel("Price")
    ax.set_ylabel("Cumulative Size")
    ax.set_title("Cumulative Depth Chart")
    ax.legend()

    # Hover using mplcursors if available and requested
    if hover:
        try:
            import mplcursors

            def _format(sel):
                x, y = sel.target
                return f"Price: {x:.4f}\nCumSize: {y:.4f}"

            mplcursors.cursor(ax.lines, hover=True).connect("add", lambda sel: sel.annotation.set_text(_format(sel)))
        except Exception:
            # mplcursors optional
            pass

    plt.tight_layout()
    plt.savefig(savepath)
    plt.close(fig)

    saved = os.path.abspath(savepath)
    print(f"Saved depth chart to: {saved}")

    # Optional interactive version using plotly
    if interactive:
        try:
            import plotly.graph_objects as go
            import html

            ipath = interactive_path if interactive_path else os.path.splitext(savepath)[0] + ".html"

            figly = go.Figure()
            if not asks.empty:
                figly.add_trace(go.Scatter(x=asks["price"].tolist(), y=asks["cum_size"].tolist(), mode="lines", name="Asks", line_shape="hv", fill="tozeroy", line_color="red"))
            if not bids.empty:
                figly.add_trace(go.Scatter(x=bids["price"].tolist(), y=bids["cum_size"].tolist(), mode="lines", name="Bids", line_shape="hv", fill="tozeroy", line_color="green"))

            figly.update_layout(title="Cumulative Depth Chart (Interactive)", xaxis_title="Price", yaxis_title="Cumulative Size")
            figly.write_html(ipath, include_plotlyjs='cdn')
            print(f"Saved interactive depth chart to: {os.path.abspath(ipath)}")
        except Exception as e:
            print("Interactive plot requested but plotly is not available or failed to render:", e)

    return saved


def plot_price_impact_curve(engine: 'MarketEngine', savepath: str | None = None, *, max_size: int = 500, n_points: int = 20) -> None:
    """Plot expected slippage (bps) vs market order size for BUY orders.

    Uses engine.calculate_price_impact for each tested size.
    """
    import numpy as _np
    import matplotlib.pyplot as _plt

    order_sizes = _np.linspace(10, max_size, n_points)
    impacts = []
    for size in order_sizes:
        bps = engine.calculate_price_impact('buy', int(size))
        impacts.append(bps)

    fig, ax = _plt.subplots(figsize=(10, 6))
    ax.plot(order_sizes, impacts, marker='o', linestyle='-', color='purple')
    ax.set_title("Price Impact vs. Order Size")
    ax.set_xlabel("Market Order Size (Units)")
    ax.set_ylabel("Execution Cost (Basis Points)")
    ax.grid(True, alpha=0.3)

    if savepath:
        fig.tight_layout()
        fig.savefig(savepath)
        print(f"Saved price impact curve to: {savepath}")
    else:
        _plt.show()


if __name__ == "__main__":
    run_simulation(ticks=100, seed=1)
