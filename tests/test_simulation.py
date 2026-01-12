from __future__ import annotations
import os
from pathlib import Path
import pytest

from simulate import run_simulation
from market_engine import MarketEngine
from bots import MarketMaker


def test_run_simulation_creates_plot(tmp_path: Path):
    out = tmp_path / "sim.png"
    out_path = run_simulation(ticks=10, seed=42, savepath=str(out))
    assert Path(out_path).exists(), "Simulation did not create the output plot"
    assert Path(out_path).stat().st_size > 0, "Output plot is empty"


def test_market_maker_posts_orders():
    # Quick unit check that a MarketMaker posts two orders on a tick
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    mm = MarketMaker(spread=1.0, size=1.0)
    engine.register_bot(mm)

    # Before stepping, no orders
    assert len(engine.order_book) == 0
    engine.step()
    # After one tick, the MarketMaker should have posted at least two orders
    assert len(engine.order_book) >= 2
    sides = {o['side'] for o in engine.order_book}
    assert 'buy' in sides and 'sell' in sides


def test_sweep_the_book():
    """A large buy order sweeps multiple sell orders at increasing prices.

    Setup:
    - Place three sell orders at prices [105, 106, 107] with sizes [1, 2, 3]
    - Place one large buy order with price 110 and size 6

    Expectation:
    - Three trades occur in order and trade prices correspond to midpoints with the buy price
    - Trade sizes match available sizes
    - The order book is empty after matching
    """

    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)

    # Place sell orders (best to worst)
    sells = [
        {'side': 'sell', 'price': 105.0, 'size': 1.0, 'bot': None},
        {'side': 'sell', 'price': 106.0, 'size': 2.0, 'bot': None},
        {'side': 'sell', 'price': 107.0, 'size': 3.0, 'bot': None},
    ]
    for s in sells:
        engine.place_order(s)

    # Large buy that should sweep all sells
    buy = {'side': 'buy', 'price': 110.0, 'size': 6.0, 'bot': None}
    engine.place_order(buy)

    # Run matching directly
    engine._match_orders()

    # Verify three trades occurred
    assert len(engine.trade_history) == 3

    # Expected trade prices are midpoints with the buy price
    expected_prices = [0.5 * (110.0 + p) for p in [105.0, 106.0, 107.0]]
    actual_prices = [round(t['price'], 6) for t in engine.trade_history]
    assert actual_prices == [round(p, 6) for p in expected_prices]

    # Expected sizes
    expected_sizes = [1.0, 2.0, 3.0]
    actual_sizes = [t['size'] for t in engine.trade_history]
    assert actual_sizes == expected_sizes

    # Book should be empty
    assert engine.order_book == []


def test_partial_fill_remaining():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)

    # One large sell order and a smaller buy -> remaining sell should be left
    engine.place_order({'side': 'sell', 'price': 105.0, 'size': 5.0, 'bot': None})
    engine.place_order({'side': 'buy', 'price': 105.0, 'size': 2.0, 'bot': None})

    engine._match_orders()

    # One trade of size 2, remaining sell size 3 in the book
    assert len(engine.trade_history) == 1
    assert engine.trade_history[0]['size'] == 2.0
    assert len(engine.order_book) == 1
    assert engine.order_book[0]['side'] == 'sell' and engine.order_book[0]['size'] == 3.0


def test_price_time_priority():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)

    # Two sells at same price; first should be consumed before the second (time priority)
    engine.place_order({'side': 'sell', 'price': 105.0, 'size': 3.0, 'bot': 'A'})
    engine.place_order({'side': 'sell', 'price': 105.0, 'size': 3.0, 'bot': 'B'})

    # Buy that partially fills both
    engine.place_order({'side': 'buy', 'price': 105.0, 'size': 4.0, 'bot': None})

    engine._match_orders()

    # Expect two trades: 3 then 1
    sizes = [t['size'] for t in engine.trade_history]
    assert sizes == [3.0, 1.0]

    # Remaining order should be the second sell (bot 'B') with size 2
    assert len(engine.order_book) == 1
    assert engine.order_book[0]['bot'] == 'B' and engine.order_book[0]['size'] == 2.0
