from __future__ import annotations
import math

from market_engine import MarketEngine
from bots import MarketMaker, SplittingBot


def test_splitting_reduces_slippage():
    """Demonstrate that splitting a large buy into slices while a MarketMaker
    provides ongoing liquidity reduces average impact compared to an immediate
    sweep against a deep book.
    """
    # Setup a deep book (expensive asks) and a market maker that posts 1 unit per tick
    engine_single = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    # initial deep asks
    engine_single.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    engine_single.place_order({'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None})
    engine_single.place_order({'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None})

    # MarketMaker posts 1 unit ask at ~100 each tick
    mm = MarketMaker(spread=1.0, size=1.0, jitter=0.0)
    engine_single.register_bot(mm)

    # Immediate single-sweep impact (no time for MM to add new liquidity)
    bps_single = engine_single.calculate_price_impact('buy', 6)

    # Now test splitting over 6 ticks while MM posts 1 unit per tick
    engine_split = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    engine_split.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    engine_split.place_order({'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None})
    engine_split.place_order({'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None})
    engine_split.register_bot(mm)  # mm will post each tick

    sb = SplittingBot()
    engine_split.register_bot(sb)

    # start a 6-unit buy split into 6 slices
    sb.start_order('buy', total_size=6.0, slices=6)

    # run for 6 ticks
    for _ in range(6):
        engine_split.step()

    # compute average execution price from the splitting bot's recorded executions
    total_executed = sum(r['executed_size'] for r in sb.executions)
    assert total_executed > 0
    total_cost = sum((r['vwap'] or 0.0) * r['executed_size'] for r in sb.executions)
    avg_price_split = total_cost / total_executed

    # mid price at start (best_bid + best_ask)/2
    # ensure we can compute mid (we had no bids initially so mm posted buys too on ticks)
    bids = [o for o in engine_split.order_book if o['side'] == 'buy']
    asks = [o for o in engine_split.order_book if o['side'] == 'sell']
    best_bid = max([b['price'] for b in bids]) if bids else None
    best_ask = min([a['price'] for a in asks]) if asks else None
    if best_bid is not None and best_ask is not None:
        mid = 0.5 * (best_bid + best_ask)
        impact_split_bps = (avg_price_split / mid - 1.0) * 10000.0
    else:
        impact_split_bps = 0.0

    # Splitting should reduce impact relative to the immediate sweep scenario
    assert impact_split_bps < bps_single
