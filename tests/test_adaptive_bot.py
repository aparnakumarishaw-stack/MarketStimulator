from __future__ import annotations

from market_engine import MarketEngine
from bots import MarketMaker, SplittingBot, AdaptiveSplittingBot


def test_adaptive_vs_splitting_improves_impact():
    # Setup: deep initial asks, and a market maker that creates 1 unit per tick
    base_engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    base_engine.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    base_engine.place_order({'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None})
    base_engine.place_order({'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None})

    mm = MarketMaker(spread=1.0, size=1.0, jitter=0.0)

    # Run simple SplittingBot over 6 ticks
    eng_split = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    eng_split.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    eng_split.place_order({'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None})
    eng_split.place_order({'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None})
    eng_split.register_bot(mm)
    sb = SplittingBot()
    eng_split.register_bot(sb)
    sb.start_order('buy', total_size=6.0, slices=6)
    for _ in range(6):
        eng_split.step()

    total_executed_split = sum(r['executed_size'] for r in sb.executions)
    total_cost_split = sum((r['vwap'] or 0.0) * r['executed_size'] for r in sb.executions)
    avg_price_split = total_cost_split / total_executed_split

    # Adaptive bot
    eng_adapt = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    eng_adapt.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    eng_adapt.place_order({'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None})
    eng_adapt.place_order({'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None})
    eng_adapt.register_bot(mm)
    ab = AdaptiveSplittingBot(aggressiveness=0.5, min_slice=0.1, max_slice=2.0)
    eng_adapt.register_bot(ab)
    ab.start_order('buy', total_size=6.0)
    for _ in range(12):
        eng_adapt.step()
        if not ab.active:
            break

    total_executed_adapt = sum(r['executed_size'] for r in ab.executions)
    total_cost_adapt = sum((r['vwap'] or 0.0) * r['executed_size'] for r in ab.executions)
    # if no executions, fail the test
    assert total_executed_adapt > 0
    avg_price_adapt = total_cost_adapt / total_executed_adapt

    # Compare using mid price roughly at the time (use last engine state mid)
    bids = [o for o in eng_adapt.order_book if o['side'] == 'buy']
    asks = [o for o in eng_adapt.order_book if o['side'] == 'sell']
    best_bid = max([b['price'] for b in bids]) if bids else None
    best_ask = min([a['price'] for a in asks]) if asks else None
    if best_bid is not None and best_ask is not None:
        mid = 0.5 * (best_bid + best_ask)
    else:
        mid = 100.0

    impact_split_bps = (avg_price_split / mid - 1.0) * 10000.0
    impact_adapt_bps = (avg_price_adapt / mid - 1.0) * 10000.0

    assert impact_adapt_bps <= impact_split_bps
