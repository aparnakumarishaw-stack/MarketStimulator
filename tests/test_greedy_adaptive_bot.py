from __future__ import annotations

from market_engine import MarketEngine
from bots import MarketMaker, SplittingBot, AdaptiveSplittingBot, GreedyAdaptiveBot


def test_greedy_improves_over_adaptive_and_splitting():
    # Setup: deep initial asks and a market maker that posts 1 unit per tick
    mm = MarketMaker(spread=1.0, size=1.0, jitter=0.0)

    # Baseline splitting
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

    # Adaptive
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
    avg_price_adapt = total_cost_adapt / total_executed_adapt

    # Greedy
    eng_g = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    eng_g.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    eng_g.place_order({'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None})
    eng_g.place_order({'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None})
    eng_g.register_bot(mm)
    g = GreedyAdaptiveBot()
    eng_g.register_bot(g)
    g.start_order('buy', total_size=6.0)
    for _ in range(12):
        eng_g.step()
        if not g.active:
            break

    total_executed_g = sum(r['executed_size'] for r in g.executions)
    total_cost_g = sum((r['vwap'] or 0.0) * r['executed_size'] for r in g.executions)
    avg_price_g = total_cost_g / total_executed_g

    # Compare using last mid
    bids = [o for o in eng_g.order_book if o['side'] == 'buy']
    asks = [o for o in eng_g.order_book if o['side'] == 'sell']
    if bids and asks:
        mid = 0.5 * (max(b['price'] for b in bids) + min(a['price'] for a in asks))
    else:
        mid = 100.0

    impact_split_bps = (avg_price_split / mid - 1.0) * 10000.0
    impact_adapt_bps = (avg_price_adapt / mid - 1.0) * 10000.0
    impact_g_bps = (avg_price_g / mid - 1.0) * 10000.0

    # Greedy should be as good or better than simple adaptive and splitting
    assert impact_g_bps <= impact_adapt_bps + 1e-9
    assert impact_g_bps <= impact_split_bps + 1e-9
