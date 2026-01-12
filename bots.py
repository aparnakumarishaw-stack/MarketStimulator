"""bots.py — simple bot implementations for MarketStimulator

Currently implements:
- MarketMaker: places symmetric buy and sell limit orders around engine.true_price
"""
from __future__ import annotations
import numpy as np
from typing import Any, Dict

class MarketMaker:
    """A simple liquidity provider that posts a buy and a sell around the true price.

    Parameters
    ----------
    spread: float
        Total spread between posted ask and bid (ask = center + spread/2)
    size: float
        Order size for each posted limit order
    jitter: float
        Standard deviation of small noise added to prices to avoid perfect symmetry
    """

    def __init__(self, spread: float = 1.0, size: float = 1.0, jitter: float = 0.05, rng: np.random.Generator | None = None):
        self.spread = float(spread)
        self.size = float(size)
        self.jitter = float(jitter)
        self.rng = rng if rng is not None else np.random.default_rng()

    def on_tick(self, engine: Any) -> None:
        center = float(engine.true_price)
        mid = center
        # Small random jitter so orders are not exactly symmetric every tick
        buy_price = mid - self.spread / 2.0 + float(self.rng.normal(0, self.jitter))
        sell_price = mid + self.spread / 2.0 + float(self.rng.normal(0, self.jitter))

        buy_order: Dict[str, Any] = {'side': 'buy', 'price': float(buy_price), 'size': self.size, 'bot': self}
        sell_order: Dict[str, Any] = {'side': 'sell', 'price': float(sell_price), 'size': self.size, 'bot': self}

        engine.place_order(buy_order)
        engine.place_order(sell_order)


class NoiseTrader:
    """Posts random limit orders around the current true price to add liquidity/noise.

    Parameters
    ----------
    intensity: float
        Controls how many orders per tick (mean around intensity)
    spread: float
        Typical distance from true price
    size_mean: float
        Mean order size
    """

    def __init__(self, intensity: float = 2.0, spread: float = 2.0, size_mean: float = 1.0, rng: np.random.Generator | None = None):
        self.intensity = float(intensity)
        self.spread = float(spread)
        self.size_mean = float(size_mean)
        self.rng = rng if rng is not None else np.random.default_rng()

    def on_tick(self, engine: Any) -> None:
        n = max(0, int(self.rng.poisson(self.intensity)))
        center = float(engine.true_price)
        for _ in range(n):
            side = 'buy' if self.rng.random() < 0.5 else 'sell'
            price = center + self.rng.normal(0, self.spread)
            size = max(0.01, float(self.rng.exponential(self.size_mean)))
            engine.place_order({'side': side, 'price': float(price), 'size': size, 'bot': self})


class InformedTrader:
    """Occasionally submits aggressive trades informed by the latent true value.

    Parameters
    ----------
    activity_prob: float
        Probability of acting on each tick
    size: float
        Size of market sweep order when acting
    direction: Optional[str]
        If set to 'buy' or 'sell', forces that action when active. If None, picks randomly.
    """

    def __init__(self, activity_prob: float = 0.05, size: float = 5.0, direction: str | None = None, rng: np.random.Generator | None = None):
        self.activity_prob = float(activity_prob)
        self.size = float(size)
        self.direction = direction
        self.rng = rng if rng is not None else np.random.default_rng()

    def on_tick(self, engine: Any) -> None:
        if self.rng.random() > self.activity_prob:
            return
        mid = float(engine.true_price)
        side = None
        if self.direction in ('buy', 'sell'):
            side = self.direction
        else:
            side = 'buy' if self.rng.random() < 0.5 else 'sell'

        if side == 'buy':
            engine.place_order({'side': 'buy', 'price': mid + 1e6, 'size': self.size, 'bot': self})
        else:
            engine.place_order({'side': 'sell', 'price': mid - 1e6, 'size': self.size, 'bot': self})


class SplittingBot:
    """A simple TWAP-style splitting bot.

    Behavior:
    - Call `start_order(side, total_size, slices)` to begin an execution
    - On each tick, the bot executes one slice by calling `engine.execute_market_order`
      which performs a market sweep for the slice size.
    - Records slices in `executions` for inspection in tests.

    Parameters
    ----------
    slice_size: float | None
        Optional fixed slice size (overrides `slices` provided to start_order)
    """

    def __init__(self, slice_size: float | None = None):
        self.slice_size = None if slice_size is None else float(slice_size)
        self.active = False
        self.side = None
        self.total = 0.0
        self.remaining = 0.0
        self.slices = 0
        self.slice = 0
        self.executions: list[dict] = []

    def start_order(self, side: str, total_size: float, slices: int | None = None) -> None:
        self.side = str(side)
        self.total = float(total_size)
        if self.slice_size is not None:
            # fixed slice size case
            self.slices = int(max(1, round(self.total / self.slice_size)))
        else:
            self.slices = int(slices) if slices is not None else max(1, int(self.total))
        self.remaining = float(self.total)
        self.slice = 0
        self.active = True
        self.executions = []

    def on_tick(self, engine: Any) -> None:
        if not self.active or self.remaining <= 0:
            return
        # compute this tick's slice
        target_slices_left = max(1, self.slices - self.slice)
        this_slice = float(self.slice_size) if self.slice_size is not None else (self.remaining / target_slices_left)
        this_slice = min(this_slice, self.remaining)

        # execute a market slice
        res = engine.execute_market_order(self.side, this_slice)
        self.executions.append(res)
        self.remaining -= res['executed_size']
        self.slice += 1
        if self.remaining <= 0 or self.slice >= self.slices:
            self.active = False


class AdaptiveSplittingBot:
    """Adaptive splitting bot that adjusts slice sizes based on visible depth.

    Strategy (simple heuristic):
    - On each tick, read `engine.get_cumulative_depth()` and determine the available
      immediate liquidity at the best price level for the passive side.
    - Take a fraction (`aggressiveness`) of that immediate liquidity as the slice size,
      bounded between `min_slice` and `max_slice` and not exceeding remaining size.
    - This keeps slices small when visible depth is thin, and larger when liquidity is deep.

    Parameters
    ----------
    aggressiveness: float
        Fraction of best-level visible liquidity to consume (0 < aggressiveness <= 1)
    min_slice: float
        Minimum slice size to execute per tick
    max_slice: float
        Maximum slice size per tick
    """

    def __init__(self, aggressiveness: float = 0.5, min_slice: float = 0.1, max_slice: float = 10.0):
        self.aggressiveness = float(aggressiveness)
        self.min_slice = float(min_slice)
        self.max_slice = float(max_slice)

        self.active = False
        self.side = None
        self.total = 0.0
        self.remaining = 0.0
        self.executions: list[dict] = []

    def start_order(self, side: str, total_size: float) -> None:
        self.side = str(side)
        self.total = float(total_size)
        self.remaining = float(total_size)
        self.active = True
        self.executions = []

    def _best_visible_liquidity(self, engine: Any) -> float:
        df = engine.get_cumulative_depth()
        if df.empty:
            return 0.0
        # For buy orders we care about asks, for sell orders we care about bids
        target_side = 'sell' if self.side == 'buy' else 'buy'
        s = df[df['side'] == target_side]
        if s.empty:
            return 0.0
        # best level is first row in csv ordering (our get_cumulative_depth returns best first for each side)
        best_level = s.iloc[0]
        return float(best_level['cum_size'])

    def on_tick(self, engine: Any) -> None:
        if not self.active or self.remaining <= 0:
            return

        visible = self._best_visible_liquidity(engine)
        this_slice = max(self.min_slice, self.aggressiveness * visible)
        this_slice = min(this_slice, self.max_slice, self.remaining)

        res = engine.execute_market_order(self.side, this_slice)
        self.executions.append(res)
        self.remaining -= res['executed_size']

        # If nothing executed (no visible liquidity), we still advance but do not mark complete
        if self.remaining <= 0:
            self.active = False


class GreedyLookaheadBot:
    """Greedy lookahead bot that simulates multiple future slices and chooses the
    candidate that minimizes the estimated average execution price over a horizon.

    Parameters
    ----------
    horizon: int
        Number of future slices to simulate (including the immediate slice)
    candidates: iterable[float] | None
        Candidate slice sizes to test (falls back to defaults used by GreedyAdaptiveBot)
    mm_assume_size: float
        When simulating future ticks, assume market makers add this much liquidity per tick at the best level (heuristic)
    """

    def __init__(self, horizon: int = 3, candidates: list[float] | None = None, mm_assume_size: float = 1.0):
        self.horizon = int(horizon)
        if candidates is None:
            self.candidates = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
        else:
            self.candidates = [float(c) for c in candidates]
        self.mm_assume_size = float(mm_assume_size)

        self.active = False
        self.side = None
        self.total = 0.0
        self.remaining = 0.0
        self.executions: list[dict] = []

    def start_order(self, side: str, total_size: float) -> None:
        self.side = str(side)
        self.total = float(total_size)
        self.remaining = float(total_size)
        self.active = True
        self.executions = []

    def _simulate_with_candidate(self, engine: Any, first_slice: float) -> float:
        """Return estimated average execution price (total_cost / total_executed)
        when taking `first_slice` now and then greedy repeating of `first_slice` for
        the remaining horizon on a simulated book (adding heuristic MM liquidity each tick).
        """
        # start from a copy of the book
        sim_book = [dict(o) for o in engine.order_book]
        total_cost = 0.0
        total_executed = 0.0

        for step in range(self.horizon):
            s = first_slice if step == 0 else first_slice
            if s <= 0:
                break
            res = engine.simulate_market_order(self.side, s, book=sim_book)
            executed = res['executed_size']
            if executed > 0 and res['vwap'] is not None:
                total_cost += executed * res['vwap']
                total_executed += executed
            # update sim_book from result
            sim_book = res['book']

            # heuristic: assume market makers add some liquidity at the best level
            # compute mid and add one ask (if buying) or bid (if selling)
            bids = [o for o in sim_book if o['side'] == 'buy']
            asks = [o for o in sim_book if o['side'] == 'sell']
            if bids and asks:
                best_bid = max(b['price'] for b in bids)
                best_ask = min(a['price'] for a in asks)
                mid = 0.5 * (best_bid + best_ask)
                # add liquidity on passive side
                add_price = mid + 0.5 if self.side == 'buy' else mid - 0.5
                new_order = {'side': 'sell' if self.side == 'buy' else 'buy', 'price': float(add_price), 'size': float(self.mm_assume_size), 'bot': None, '_id': -9999 - step}
                sim_book.append(new_order)
            else:
                # if no bids/asks, add a synthetic level
                add_price = engine.true_price + 1.0 if self.side == 'buy' else engine.true_price - 1.0
                new_order = {'side': 'sell' if self.side == 'buy' else 'buy', 'price': float(add_price), 'size': float(self.mm_assume_size), 'bot': None, '_id': -9999 - step}
                sim_book.append(new_order)

        if total_executed == 0:
            return float('inf')
        return total_cost / total_executed

    def _choose_slice(self, engine: Any) -> float:
        best_s = self.candidates[0]
        best_avg = float('inf')
        for c in self.candidates:
            s = max(0.0, min(c, self.remaining))
            if s <= 0:
                continue
            avg_price = self._simulate_with_candidate(engine, s)
            if avg_price < best_avg:
                best_avg = avg_price
                best_s = s
        return float(best_s)

    def on_tick(self, engine: Any) -> None:
        if not self.active or self.remaining <= 0:
            return

        this_slice = self._choose_slice(engine)
        this_slice = min(this_slice, self.remaining)

        res = engine.execute_market_order(self.side, this_slice)
        self.executions.append(res)
        self.remaining -= res['executed_size']

        if self.remaining <= 0:
            self.active = False


class GreedyAdaptiveBot:
    """Greedy bot that picks the slice size each tick by minimizing estimated
    immediate execution price per unit using `engine.calculate_price_impact`.

    Parameters
    ----------
    candidates: iterable[float] | None
        Candidate slice sizes to consider. If None, a default log-spaced grid is used.
    min_slice, max_slice: float
        Bounds on the slice sizes.
    """

    def __init__(self, candidates: list[float] | None = None, min_slice: float = 0.1, max_slice: float = 10.0):
        if candidates is None:
            # default candidates: 0.1, 0.2, 0.5, 1, 2, 5, 10
            self.candidates = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
        else:
            self.candidates = [float(c) for c in candidates]
        self.min_slice = float(min_slice)
        self.max_slice = float(max_slice)

        self.active = False
        self.side = None
        self.total = 0.0
        self.remaining = 0.0
        self.executions: list[dict] = []

    def start_order(self, side: str, total_size: float) -> None:
        self.side = str(side)
        self.total = float(total_size)
        self.remaining = float(total_size)
        self.active = True
        self.executions = []

    def _choose_slice(self, engine: Any) -> float:
        # compute mid price
        bids = [o for o in engine.order_book if o['side'] == 'buy']
        asks = [o for o in engine.order_book if o['side'] == 'sell']
        if not bids or not asks:
            # no mid defined; fall back to min_slice
            return self.min_slice
        best_bid = max([b['price'] for b in bids])
        best_ask = min([a['price'] for a in asks])
        mid = 0.5 * (best_bid + best_ask)

        best_candidate = self.min_slice
        best_price_per_unit = float('inf')

        for c in self.candidates:
            s = max(self.min_slice, min(self.max_slice, min(c, self.remaining)))
            if s <= 0:
                continue
            # estimate bps using the engine's simulator (non-mutating)
            bps = engine.calculate_price_impact(self.side, int(max(1, round(s))))
            # convert bps back to estimated avg execution price
            if self.side == 'buy':
                est_price = mid * (1.0 + bps / 10000.0)
            else:
                est_price = mid * (1.0 - bps / 10000.0)
            # cost per unit is est_price; for buys lower is better
            if est_price < best_price_per_unit:
                best_price_per_unit = est_price
                best_candidate = s

        return float(best_candidate)

    def on_tick(self, engine: Any) -> None:
        if not self.active or self.remaining <= 0:
            return

        this_slice = self._choose_slice(engine)
        this_slice = min(this_slice, self.remaining)

        res = engine.execute_market_order(self.side, this_slice)
        self.executions.append(res)
        self.remaining -= res['executed_size']

        if self.remaining <= 0:
            self.active = False

