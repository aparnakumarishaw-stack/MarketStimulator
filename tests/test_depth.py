from pathlib import Path
from market_engine import MarketEngine
from simulate import plot_depth


def test_get_cumulative_depth_basic():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    engine.place_order({'side': 'buy', 'price': 100.0, 'size': 1.0, 'bot': None})
    engine.place_order({'side': 'buy', 'price': 99.0, 'size': 2.0, 'bot': None})
    engine.place_order({'side': 'sell', 'price': 101.0, 'size': 3.0, 'bot': None})

    df = engine.get_cumulative_depth()

    bids = df[df['side'] == 'buy'].sort_values('price', ascending=False)
    assert list(bids['cum_size']) == [1.0, 3.0]

    asks = df[df['side'] == 'sell']
    assert list(asks['cum_size']) == [3.0]


def test_plot_depth_creates_file(tmp_path: Path):
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    engine.place_order({'side': 'buy', 'price': 100.0, 'size': 1.0, 'bot': None})
    engine.place_order({'side': 'sell', 'price': 101.0, 'size': 1.0, 'bot': None})

    out = tmp_path / 'depth.png'
    path = plot_depth(engine, savepath=str(out))
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0
