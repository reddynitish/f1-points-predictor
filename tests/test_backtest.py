import json
from pathlib import Path

from test_leakage import fixture

from f1_points.backtest import run_backtest, summarize, top10_hits

CONFIG_PATH = Path(__file__).parents[1] / 'configs' / 'final.json'


def test_backtest_scores_only_completed_races_without_using_their_outcomes():
    events, entries, labels = fixture()
    frame = run_backtest(events, entries, labels, 2024, json.loads(CONFIG_PATH.read_text()))
    assert set(frame['event_id']) == {'2024-02', '2024-03'}  # 2024-01 has no earlier races to fit on
    flipped = labels.copy()
    flipped.loc[flipped['event_id'] == '2024-03', 'race_points'] = 0.0
    again = run_backtest(events, entries, flipped, 2024, json.loads(CONFIG_PATH.read_text()))
    target = frame['event_id'] == '2024-03'
    assert frame.loc[target, 'p_B1'].tolist() == again.loc[again['event_id'] == '2024-03', 'p_B1'].tolist()
    assert (
        frame.loc[target, 'scored_points'].tolist()
        != again.loc[again['event_id'] == '2024-03', 'scored_points'].tolist()
    )
    summary = summarize(frame, 2024, CONFIG_PATH)
    assert summary['races'] == 2 and 'not forecasts' in summary['framing']


def test_top10_hits_counts_scorers_among_ten_most_likely():
    import pandas as pd

    frame = pd.DataFrame(
        {'event_id': ['A'] * 12, 'p': [1 - i / 12 for i in range(12)], 'scored_points': [1] * 8 + [0, 0, 1, 1]}
    )
    assert top10_hits(frame, 'p')['A'] == 8
