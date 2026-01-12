"""Depth-snapshot-based simulation runner for evaluating execution strategies."""
from __future__ import annotations
import json
from typing import Any, Callable, Dict, List, Tuple
from market_engine import MarketEngine


class SimulationRunner:
    """Run a simple snapshot-driven simulation.

    Usage:
        runner = SimulationRunner(snapshots)
        runner.run_strategy(MyBotClass(), side='buy', total_size=6.0)

    The runner returns a dict with executed, avg_price, total_cost, impact_bps (w.r.t snapshot mid)
    """

    def __init__(self, snapshots: List[List[Dict[str, Any]]]):
        self.snapshots = snapshots

    @staticmethod
    def load_snapshot_file(path: str) -> List[List[Dict[str, Any]]]:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def run_strategy(self, bot_factory: Callable[[], Any], *, side: str = 'buy', total_size: float = 6.0, max_ticks: int | None = None) -> Dict[str, Any]:
        engine = MarketEngine(init_price=100.0, vol=0.0, rng=None)
        bot = bot_factory()
        # Give bot a chance to be registered if needed
        engine.register_bot(bot)

        # Start the execution on the bot; accommodate differing start_order signatures
        try:
            bot.start_order(side=side, total_size=total_size)
        except TypeError:
            try:
                bot.start_order(side, total_size, slices=int(total_size))
            except Exception:
                # if bot has no start_order, continue (it may act without explicit start)
                pass

        remaining = float(total_size)
        executed_total = 0.0
        total_cost = 0.0

        ticks = 0
        for snap in self.snapshots:
            if max_ticks is not None and ticks >= max_ticks:
                break
            ticks += 1
            engine.load_snapshot(snap)
            # Prefer calling the bot directly. If it fails, fall back to engine.step()
            try:
                bot.on_tick(engine)
            except Exception:
                try:
                    engine.step()
                except Exception:
                    pass

            # collect executions recorded by the bot
            if hasattr(bot, 'executions'):
                # sum any new executions since last tick
                for r in bot.executions:
                    # executions may include partial fills; ensure we count
                    executed = r.get('executed_size', 0.0)
                    vwap = r.get('vwap', None)
                    if executed > 0:
                        executed_total += executed
                        total_cost += (vwap or 0.0) * executed
                        remaining = max(0.0, remaining - executed)
                # clear for next tick (store history only in runner if desired)
                bot.executions = []

            if remaining <= 0:
                break

        avg_price = (total_cost / executed_total) if executed_total > 0 else None

        # compute impact bps with respect to last snapshot mid
        last_bids = [o for o in (self.snapshots[ticks-1] if ticks>0 else []) if o['side']=='buy']
        last_asks = [o for o in (self.snapshots[ticks-1] if ticks>0 else []) if o['side']=='sell']
        if last_bids and last_asks and avg_price is not None:
            mid = 0.5 * (max(b['price'] for b in last_bids) + min(a['price'] for a in last_asks))
            impact_bps = (avg_price / mid - 1.0) * 10000.0 if side == 'buy' else (1.0 - avg_price / mid) * 10000.0
        else:
            impact_bps = None

        return {'executed': executed_total, 'avg_price': avg_price, 'impact_bps': impact_bps, 'remaining': remaining}


if __name__ == '__main__':
    # Quick smoke run using the sample file
    snaps = SimulationRunner.load_snapshot_file('scripts/data/sample_depth_snapshots.json')
    runner = SimulationRunner(snaps)
    from bots import SplittingBot
    res = runner.run_strategy(lambda: SplittingBot(), side='buy', total_size=6.0)
    print(res)