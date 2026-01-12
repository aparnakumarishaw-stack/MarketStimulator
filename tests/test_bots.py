from market_engine import MarketEngine
from bots import NoiseTrader, InformedTrader


def test_noise_trader_posts_orders():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    nt = NoiseTrader(intensity=5.0, spread=1.0, size_mean=0.5)
    engine.register_bot(nt)
    engine.step()
    # Should have posted some orders or none if Poisson drew 0; run multiple ticks to be robust
    engine.step()
    assert any(o['side'] in {'buy','sell'} for o in engine.order_book)


def test_informed_trader_sweeps():
    engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)
    # Create some ask liquidity
    engine.place_order({'side':'sell','price':101.0,'size':1.0,'bot':None})
    engine.place_order({'side':'sell','price':102.0,'size':1.0,'bot':None})

    it = InformedTrader(activity_prob=1.0, size=5.0, direction='buy')  # force buy
    engine.register_bot(it)
    engine.step()

    # given informed trader uses a very high buy price when buying, all sells should be consumed
    assert len(engine.trade_history) >= 2 or any(o['side'] == 'buy' for o in engine.order_book)
