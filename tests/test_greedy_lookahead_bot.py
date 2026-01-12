from __future__ import annotations

from market_engine import MarketEngine
from bots import MarketMaker, GreedyAdaptiveBot, GreedyLookaheadBot


def test_lookahead_improves_over_greedy():
    mm = MarketMaker(spread=1.0, size=1.0, jitter=0.0)

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

    eng_l = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    eng_l.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    eng_l.place_order({'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None})
    eng_l.place_order({'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None})
    eng_l.register_bot(mm)
    l = GreedyLookaheadBot(horizon=3, mm_assume_size=1.0)
    eng_l.register_bot(l)
    l.start_order('buy', total_size=6.0)
    for _ in range(12):
        eng_l.step()
        if not l.active:
            break

    total_executed_l = sum(r['executed_size'] for r in l.executions)
    total_cost_l = sum((r['vwap'] or 0.0) * r['executed_size'] for r in l.executions)
    avg_price_l = total_cost_l / total_executed_l

    # Use last mid for comparison
    bids = [o for o in eng_l.order_book if o['side'] == 'buy']
    asks = [o for o in eng_l.order_book if o['side'] == 'sell']
    if bids and asks:
        mid = 0.5 * (max(b['price'] for b in bids) + min(a['price'] for a in asks))
    else:
        mid = 100.0

    impact_g_bps = (avg_price_g / mid - 1.0) * 10000.0
    impact_l_bps = (avg_price_l / mid - 1.0) * 10000.0

    assert impact_l_bps <= impact_g_bps + 1e-6
