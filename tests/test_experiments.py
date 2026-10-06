import json

import numpy as np
import pandas as pd

from f1_points.experiments import run_selection


def synthetic_dataset(directory, test_labels):
    rng = np.random.default_rng(0)
    rows = []
    for season in range(2018, 2026):
        for round_number in (1, 2):
            for rank in range(1, 9):
                rows.append(
                    {
                        'event_id': f'{season}-{round_number:02d}',
                        'driver_id': f'd{rank}',
                        'season': season,
                        'round': round_number,
                        'qualifying_rank': rank,
                        'qualifying_rank_missing': 0,
                        'field_size': 8,
                        'qualifying_percentile': (rank - 1) / 7,
                        'driver_points_rate_last5': rng.uniform(),
                        'driver_finish_mean_last5': rng.uniform(1, 8),
                        'driver_dnf_rate_last5': rng.uniform(0, 0.3),
                        'driver_history_count': 5,
                        'rookie': 0,
                        'constructor_points_rate_last5_events': rng.uniform(),
                        'constructor_history_events': 5,
                        'constructor_new': 0,
                        'circuit_id': f'c{round_number}',
                        'constructor_id': f't{(rank + 1) // 2}',
                        'scored_points': test_labels(rank) if season == 2025 else int(rank <= 4),
                    }
                )
    frame = pd.DataFrame(rows)
    directory.mkdir()
    frame.drop(columns='scored_points').to_parquet(directory / 'features.parquet')
    frame[['event_id', 'driver_id', 'scored_points']].to_parquet(directory / 'labels.parquet')


def test_selection_is_independent_of_test_season_labels(tmp_path):
    results = []
    for name, test_labels in [('a', lambda rank: int(rank <= 4)), ('b', lambda rank: int(rank > 4))]:
        synthetic_dataset(tmp_path / name, test_labels)
        report = run_selection(tmp_path / name, tmp_path / f'{name}.json', tmp_path / f'{name}-config.json')
        results.append(([(c['candidate'], c['race_brier']) for c in report['candidates']], report['selected']))
        assert json.loads((tmp_path / f'{name}-config.json').read_text())['test_season'] == 2025
    assert results[0] == results[1]
