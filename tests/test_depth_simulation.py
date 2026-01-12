from __future__ import annotations

from scripts.depth_simulation import SimulationRunner
from bots import GreedyAdaptiveBot, GreedyLookaheadBot


def test_lookahead_vs_greedy_on_snapshots():
    snaps = SimulationRunner.load_snapshot_file('scripts/data/sample_depth_snapshots.json')
    runner = SimulationRunner(snaps)

    res_g = runner.run_strategy(lambda: GreedyAdaptiveBot(), side='buy', total_size=6.0)
    res_l = runner.run_strategy(lambda: GreedyLookaheadBot(horizon=3, mm_assume_size=1.0), side='buy', total_size=6.0)

    # Ensure both executed non-zero amounts
    assert res_g['executed'] > 0
    assert res_l['executed'] > 0

    # If impact is computable for both, lookahead should be at least as good
    if res_g['impact_bps'] is not None and res_l['impact_bps'] is not None:
        assert res_l['impact_bps'] <= res_g['impact_bps'] + 1e-6