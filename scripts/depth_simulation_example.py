from __future__ import annotations
import os
from scripts.depth_simulation import SimulationRunner
from bots import SplittingBot, AdaptiveSplittingBot, GreedyAdaptiveBot, GreedyLookaheadBot

SNAP_PATH = 'scripts/data/sample_depth_snapshots.json'
ARTIFACTS = os.path.abspath('artifacts')
os.makedirs(ARTIFACTS, exist_ok=True)


def main(save_csv: str | None = None):
    snaps = SimulationRunner.load_snapshot_file(SNAP_PATH)
    runner = SimulationRunner(snaps)

    strategies = [
        ('splitting', lambda: SplittingBot()),
        ('adaptive', lambda: AdaptiveSplittingBot(aggressiveness=0.5, min_slice=0.1, max_slice=2.0)),
        ('greedy', lambda: GreedyAdaptiveBot()),
        ('lookahead', lambda: GreedyLookaheadBot(horizon=3, mm_assume_size=1.0)),
    ]

    results = []
    for name, fact in strategies:
        res = runner.run_strategy(fact, side='buy', total_size=6.0)
        results.append({'strategy': name, **res})

    csv_path = save_csv or os.path.join(ARTIFACTS, 'depth_sim_results.csv')
    import csv
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['strategy', 'executed', 'avg_price', 'impact_bps', 'remaining'])
        for r in results:
            w.writerow([r['strategy'], r['executed'], r['avg_price'], r['impact_bps'], r['remaining']])

    print('Saved results to', csv_path)
    return csv_path


if __name__ == '__main__':
    main()