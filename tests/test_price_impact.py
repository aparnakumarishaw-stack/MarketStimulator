from __future__ import annotations
import math

from market_engine import MarketEngine


def test_price_impact_buy_full_book():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)

    # add a bid so mid can be computed
    engine.place_order({'side': 'buy', 'price': 99.0, 'size': 1.0, 'bot': None})

    # add asks at increasing prices and sizes: total size = 6
    engine.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    engine.place_order({'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None})
    engine.place_order({'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None})

    # compute expected VWAP and mid
    total_cost = 105.0*1 + 106.0*2 + 107.0*3
    vwap = total_cost / 6.0
    mid = 0.5 * (99.0 + 105.0)

    expected_bps = (vwap / mid - 1.0) * 10000.0

    bps = engine.calculate_price_impact('buy', 6)
    assert math.isclose(bps, expected_bps, rel_tol=1e-9)


def test_price_impact_partial_and_no_mid():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)

    # no bids present -> mid undefined -> expect 0
    engine.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    bps = engine.calculate_price_impact('buy', 10)
    assert bps == 0.0

    # add a bid to allow mid
    engine.place_order({'side': 'buy', 'price': 95.0, 'size': 2.0, 'bot': None})

    # Only one sell of size 1 -> partial fill
    bps = engine.calculate_price_impact('buy', 5)
    assert bps > 0.0
