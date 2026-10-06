import json

import pandas as pd
import pytest

from f1_points.livetiming import LiveTimingClient, event_sessions, match_meeting, meetings_from_schedule, parse_stream

PREFIX = '2024/2024-03-02_Test_Grand_Prix/'
SCHEDULE = [
    {
        'RoundNumber': 1,
        'EventName': 'Test Grand Prix',
        'Session1': 'Practice 1',
        'Session1DateUtc': pd.Timestamp('2024-03-01 09:00'),
        'Session2': 'Qualifying',
        'Session2DateUtc': pd.Timestamp('2024-03-01 15:00'),
        'Session3': 'Practice 2',
        'Session3DateUtc': pd.Timestamp('2024-03-02 09:00'),
        'Session4': 'Race',
        'Session4DateUtc': pd.Timestamp('2024-03-02 15:00'),
        'Session5': '',
        'Session5DateUtc': pd.NaT,
    }
]
DATES = {'Practice 1': '2024-03-01', 'Qualifying': '2024-03-01', 'Practice 2': '2024-03-02', 'Race': '2024-03-02'}


def path_for(round_number, name):
    return PREFIX + DATES[name] + '_' + name.replace(' ', '_') + '/'


WEATHER = (
    '00:00:01.000{"Rainfall":"0","TrackTemp":"40.0","AirTemp":"25.0"}\n'
    '00:01:01.000{"Rainfall":"1","TrackTemp":"30.0","AirTemp":"21.0"}\n'
)
PAGES = {
    '2024/2024-03-02_Test_Grand_Prix/2024-03-01_Practice_1/TimingStats.json': json.dumps(
        {'Lines': {'1': {'PersonalBestLapTime': {'Value': '1:30.500'}}, '44': {'PersonalBestLapTime': {'Value': ''}}}}
    ),
    '2024/2024-03-02_Test_Grand_Prix/2024-03-01_Practice_1/DriverList.json': json.dumps(
        {'1': {'Tla': 'VER'}, '44': {'Tla': 'HAM'}}
    ),
    '2024/2024-03-02_Test_Grand_Prix/2024-03-01_Qualifying/WeatherData.jsonStream': WEATHER,
}


class Response:
    def __init__(self, url):
        page = url.split('/static/')[1]
        self.status_code = 200 if page in PAGES else 404
        self.content = ('﻿' + PAGES.get(page, '')).encode()

    def raise_for_status(self):
        pass


def client(tmp_path, calls):
    def fetch(url, **kwargs):
        calls.append(url)
        return Response(url)

    return LiveTimingClient(tmp_path, fetch=fetch, sleep=lambda _: None, clock=lambda: 0.0)


def test_schedule_sessions_get_utc_times_and_paths():
    meetings = meetings_from_schedule(SCHEDULE, path_for)
    assert [s['name'] for s in meetings[0]['sessions']] == ['Practice 1', 'Qualifying', 'Practice 2', 'Race']
    assert meetings[0]['sessions'][-1]['start_utc'].isoformat() == '2024-03-02T15:00:00+00:00'
    assert meetings[0]['sessions'][0]['path'] == PREFIX + '2024-03-01_Practice_1/'


def test_matching_uses_race_start_within_tolerance():
    meetings = meetings_from_schedule(SCHEDULE, path_for)
    assert match_meeting(meetings, '2024-03-02T15:00:00+00:00')['name'] == 'Test Grand Prix'
    assert match_meeting(meetings, '2024-03-10T15:00:00+00:00') is None


def test_only_practice_before_qualifying_and_weather_parsed(tmp_path):
    calls = []
    live = client(tmp_path, calls)
    record = event_sessions(live, meetings_from_schedule(SCHEDULE, path_for)[0])
    assert [p['session'] for p in record['practice']] == ['Practice 1']  # Practice 2 runs after qualifying
    assert record['practice'][0]['best_laps'] == {'1': 90.5, '44': None}
    assert record['practice'][0]['codes']['1'] == 'VER'
    assert record['qualifying_weather'] == {'samples': 2, 'rain': True, 'track_temp_mean': 35.0, 'air_temp_mean': 23.0}
    assert not any('Practice_2' in url for url in calls)


def test_cache_is_reused_offline_and_missing_pages_are_recorded(tmp_path):
    calls = []
    live = client(tmp_path, calls)
    body, manifest = live.get('2024/missing.json')
    assert body is None and manifest['status'] == 404
    count = len(calls)
    assert live.get('2024/missing.json', offline=True)[0] is None
    assert len(calls) == count
    with pytest.raises(FileNotFoundError):
        LiveTimingClient(tmp_path / 'empty').get('2024/Index.json', offline=True)


def test_stream_parsing():
    assert parse_stream('00:00:01.5{"a": 1}\n\n') == [('00:00:01.5', {'a': 1})]
