from market_engine import MarketEngine
import math


def test_market_order_vwap_and_full_fill():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)

    # Place sells at 105 (1), 106 (2), 107 (3) -> total 6
    engine.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    engine.place_order({'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None})
    engine.place_order({'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None})

    result = engine.execute_market_order('buy', 6.0)

    assert math.isclose(result['executed_size'], 6.0)
    assert math.isclose(result['unfilled_size'], 0.0)

    # VWAP should equal weighted average of prices
    expected_vwap = (105.0*1 + 106.0*2 + 107.0*3) / 6.0
    assert math.isclose(result['vwap'], expected_vwap)

    # Order book should be empty for sells
    assert all(o['side'] != 'sell' for o in engine.order_book)


def test_market_order_insufficient_liquidity():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)

    engine.place_order({'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None})
    engine.place_order({'side': 'sell', 'price': 106.0, 'size': 1.0, 'bot': None})

    result = engine.execute_market_order('buy', 5.0)

    assert math.isclose(result['executed_size'], 2.0)
    assert math.isclose(result['unfilled_size'], 3.0)
    assert result['vwap'] is not None
    # Book should be empty
    assert len(engine.order_book) == 0


def test_sell_market_order_against_bids():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)

    engine.place_order({'side': 'buy', 'price': 99.0, 'size': 2.0, 'bot': None})
    engine.place_order({'side': 'buy', 'price': 98.0, 'size': 2.0, 'bot': None})

    result = engine.execute_market_order('sell', 3.0)

    assert math.isclose(result['executed_size'], 3.0)
    assert math.isclose(result['unfilled_size'], 0.0)
    # VWAP should be weighted by bid prices
    expected = (99.0*2 + 98.0*1) / 3.0
    assert math.isclose(result['vwap'], expected)