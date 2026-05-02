from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest

from services.smartwatch.contracts import FetchContext, TokenBundle
from services.smartwatch.providers.google_fit_adapter import GoogleFitAdapter


class StubGoogleFitAdapter(GoogleFitAdapter):
    def __init__(self):
        super().__init__(client_id='client-id', client_secret='client-secret')
        self._fake_token_payload = {
            'access_token': 'new-token',
            'refresh_token': 'refresh-token',
            'expires_in': 3600,
            'scope': 'scope-a scope-b',
        }
        self._fake_aggregate_response = {
            'bucket': [
                {
                    'dataset': [
                        {
                            'dataSourceId': 'derived:com.google.step_count.delta:merge',
                            'point': [
                                {'value': [{'intVal': 3500}]},
                                {'value': [{'intVal': 1500}]},
                            ],
                        },
                        {
                            'dataSourceId': 'derived:com.google.heart_rate.bpm:merge',
                            'point': [
                                {'value': [{'fpVal': 74.2}]},
                                {'value': [{'fpVal': 75.8}]},
                            ],
                        },
                        {
                            'dataSourceId': 'derived:com.google.body.temperature:merge',
                            'point': [
                                {'value': [{'fpVal': 36.7}]},
                            ],
                        },
                        {
                            'dataSourceId': 'derived:com.google.blood_pressure:merge',
                            'point': [
                                {'value': [{'fpVal': 121.0}]},
                            ],
                        },
                        {
                            'dataSourceId': 'derived:com.google.blood_glucose:merge',
                            'point': [
                                {'value': [{'fpVal': 98.5}]},
                            ],
                        },
                        {
                            'dataSourceId': 'derived:com.google.sleep.segment:merge',
                            'point': [
                                {
                                    'startTimeNanos': str(0),
                                    'endTimeNanos': str(2 * 3_600_000_000_000),
                                    'value': [{'intVal': 1}],
                                }
                            ],
                        },
                    ]
                }
            ]
        }

    def _post_form(self, url, form_data):
        return dict(self._fake_token_payload)

    def _post_json(self, url, bearer_token, payload):
        return dict(self._fake_aggregate_response)


class EdgeCaseGoogleFitAdapter(GoogleFitAdapter):
    def __init__(self, aggregate_response):
        super().__init__(client_id='client-id', client_secret='client-secret')
        self._aggregate_response = aggregate_response

    def _post_json(self, url, bearer_token, payload):
        return dict(self._aggregate_response)


class SequenceGoogleFitAdapter(GoogleFitAdapter):
    def __init__(self, responses):
        super().__init__(client_id='client-id', client_secret='client-secret')
        self._responses = list(responses)
        self.seen_aggregate_by = []

    def _post_json(self, url, bearer_token, payload):
        aggregate_by = payload.get('aggregateBy', [])
        self.seen_aggregate_by.append(
            [item.get('dataTypeName') for item in aggregate_by if isinstance(item, dict)]
        )
        if not self._responses:
            return {'bucket': []}
        return dict(self._responses.pop(0))


def test_google_fit_build_authorization_url_contains_expected_params():
    adapter = StubGoogleFitAdapter()

    auth_url = adapter.build_authorization_url(
        user_id=42,
        redirect_uri='https://example.com/callback',
        state='csrf-state',
    )

    parsed = urlparse(auth_url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == 'https'
    assert 'accounts.google.com' in parsed.netloc
    assert params['client_id'] == ['client-id']
    assert params['response_type'] == ['code']
    assert params['redirect_uri'] == ['https://example.com/callback']
    assert params['state'] == ['csrf-state:42']


def test_google_fit_exchange_and_refresh_return_token_bundle():
    adapter = StubGoogleFitAdapter()

    token_bundle = adapter.exchange_code_for_tokens(code='auth-code', redirect_uri='https://example.com/callback')
    refreshed_bundle = adapter.refresh_access_token(refresh_token='existing-refresh-token')

    assert token_bundle.access_token == 'new-token'
    assert token_bundle.refresh_token == 'refresh-token'
    assert token_bundle.expires_at is not None

    assert refreshed_bundle.access_token == 'new-token'
    assert refreshed_bundle.refresh_token == 'refresh-token'
    assert refreshed_bundle.expires_at is not None


def test_google_fit_fetch_health_payloads_maps_to_canonical_fields():
    adapter = StubGoogleFitAdapter()
    context = FetchContext(
        user_id=7,
        provider='google_fit',
        token=TokenBundle(access_token='token-value', refresh_token='rt'),
        since=datetime(2026, 3, 20, 0, 0, 0, tzinfo=timezone.utc),
    )

    payloads = adapter.fetch_health_payloads(context)

    assert len(payloads) == 1
    payload = payloads[0]

    assert payload.provider == 'google_fit'
    assert payload.heart_rate == 75
    assert payload.temperature == 36.7
    assert payload.steps == 5000
    assert payload.sleep_hours == 2.0
    assert payload.blood_pressure == 121.0
    assert payload.sugar == 98.5
    assert payload.source_record_id is not None

    service_payload = payload.to_health_service_payload()
    assert service_payload['heart_rate'] == 75
    assert service_payload['temperature'] == 36.7
    assert service_payload['steps'] == 5000
    assert service_payload['sleep_hours'] == 2.0
    assert service_payload['blood_pressure'] == 121.0
    assert service_payload['sugar'] == 98.5


def test_to_token_bundle_requires_access_token():
    adapter = GoogleFitAdapter(client_id='client-id', client_secret='client-secret')

    with pytest.raises(ValueError, match='access_token'):
        adapter._to_token_bundle({'refresh_token': 'rt'})


def test_to_ns_treats_naive_datetimes_as_local_time():
    adapter = GoogleFitAdapter(client_id='client-id', client_secret='client-secret')

    local_timezone = datetime.now().astimezone().tzinfo
    wall_time = datetime(2026, 3, 25, 14, 20, 0)
    naive_ns = adapter._to_ns(wall_time)
    local_aware_ns = adapter._to_ns(wall_time.replace(tzinfo=local_timezone))

    assert naive_ns == local_aware_ns


def test_fetch_health_payloads_returns_empty_when_no_supported_metrics():
    adapter = EdgeCaseGoogleFitAdapter(
        aggregate_response={
            'bucket': [
                {
                    'dataset': [
                        {
                            'dataSourceId': 'derived:com.unknown.metric:merge',
                            'point': [{'value': [{'fpVal': 1.0}]}],
                        }
                    ]
                }
            ]
        }
    )

    context = FetchContext(
        user_id=77,
        provider='google_fit',
        token=TokenBundle(access_token='token'),
        since=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )

    payloads = adapter.fetch_health_payloads(context)

    assert payloads == []


def test_fetch_health_payloads_ignores_invalid_cursor_and_still_maps_data():
    adapter = EdgeCaseGoogleFitAdapter(
        aggregate_response={
            'bucket': [
                {
                    'dataset': [
                        {
                            'dataSourceId': 'derived:com.google.step_count.delta:merge',
                            'point': [
                                {'value': [{'intVal': 1200}]},
                                {'value': [{'intVal': 800}]},
                            ],
                        },
                        {
                            'dataSourceId': 'derived:com.google.heart_rate.bpm:merge',
                            'point': [
                                {'value': [{'fpVal': 70.0}]},
                                {'value': [{'fpVal': 74.0}]},
                            ],
                        },
                    ]
                }
            ]
        }
    )

    context = FetchContext(
        user_id=42,
        provider='google_fit',
        token=TokenBundle(access_token='token', refresh_token='rt'),
        cursor='definitely-not-iso8601',
        since=None,
    )

    payloads = adapter.fetch_health_payloads(context)

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload.provider == 'google_fit'
    assert payload.steps == 2000
    assert payload.heart_rate == 72
    assert payload.source_record_id.startswith('aggregate:')


def test_extract_metrics_combines_multiple_points_and_buckets():
    adapter = GoogleFitAdapter(client_id='client-id', client_secret='client-secret')

    aggregate_response = {
        'bucket': [
            {
                'dataset': [
                    {
                        'dataSourceId': 'derived:com.google.step_count.delta:merge',
                        'point': [
                            {'value': [{'intVal': 500}]},
                        ],
                    },
                    {
                        'dataSourceId': 'derived:com.google.step_count.delta:merge',
                        'point': [
                            {'value': [{'intVal': 1500}]},
                        ],
                    },
                    {
                        'dataSourceId': 'derived:com.google.sleep.segment:merge',
                        'point': [
                            {
                                'startTimeNanos': str(0),
                                'endTimeNanos': str(3_600_000_000_000),
                                'value': [{'intVal': 1}],
                            }
                        ],
                    },
                    {
                        'dataSourceId': 'derived:com.google.heart_rate.summary:com.google.android.gms:aggregated',
                        'dataTypeName': 'com.google.heart_rate.summary',
                        'point': [
                            {
                                'value': [
                                    {
                                        'mapVal': [
                                            {'key': 'average', 'value': {'fpVal': 74.0}},
                                            {'key': 'max', 'value': {'fpVal': 98.0}},
                                        ]
                                    }
                                ]
                            }
                        ],
                    },
                    {
                        'dataSourceId': 'derived:com.google.body.temperature.summary:com.google.android.gms:aggregated',
                        'dataTypeName': 'com.google.body.temperature.summary',
                        'point': [
                            {
                                'value': [
                                    {
                                        'mapVal': [
                                            {'key': 'average', 'value': {'fpVal': 36.8}},
                                        ]
                                    }
                                ]
                            }
                        ],
                    },
                    {
                        'dataSourceId': 'derived:com.google.blood_pressure.summary:com.google.android.gms:aggregated',
                        'dataTypeName': 'com.google.blood_pressure.summary',
                        'point': [
                            {
                                'value': [
                                    {
                                        'mapVal': [
                                            {'key': 'blood_pressure_systolic_average', 'value': {'fpVal': 120.0}},
                                            {'key': 'blood_pressure_diastolic_average', 'value': {'fpVal': 80.0}},
                                        ]
                                    }
                                ]
                            }
                        ],
                    },
                    {
                        'dataSourceId': 'derived:com.google.blood_glucose.summary:com.google.android.gms:aggregated',
                        'dataTypeName': 'com.google.blood_glucose.summary',
                        'point': [
                            {
                                'value': [
                                    {
                                        'mapVal': [
                                            {'key': 'average', 'value': {'fpVal': 102.0}},
                                        ]
                                    }
                                ]
                            }
                        ],
                    },
                ]
            }
        ]
    }

    metrics = adapter._extract_metrics(aggregate_response)

    assert metrics['steps'] == 2000.0
    assert metrics['heart_rate'] == 74.0
    assert metrics['temperature'] == 36.8
    assert metrics['blood_pressure'] == 120.0
    assert metrics['sugar'] == 102.0
    assert metrics['sleep_hours'] == 1.0


def test_fetch_health_payloads_caps_large_steps_for_single_day_window():
    adapter = EdgeCaseGoogleFitAdapter(
        aggregate_response={
            'bucket': [
                {
                    'dataset': [
                        {
                            'dataSourceId': 'derived:com.google.step_count.delta:merge',
                            'point': [
                                {'value': [{'intVal': 99828}]},
                            ],
                        },
                    ]
                }
            ]
        }
    )

    context = FetchContext(
        user_id=88,
        provider='google_fit',
        token=TokenBundle(access_token='token', refresh_token='rt'),
        # Adapter now ignores explicit historical since for fetch strategy and
        # evaluates fixed recent day windows only.
        since=datetime(2026, 3, 30, 16, 17, 48, tzinfo=timezone.utc),
    )

    payloads = adapter.fetch_health_payloads(context)

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload.steps == 60000
    assert payload.steps <= 60000


def test_normalize_steps_caps_single_window_extreme_values():
    adapter = GoogleFitAdapter(client_id='client-id', client_secret='client-secret')

    now = datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)
    normalized = adapter._normalize_steps_for_ingestion(
        steps=120000.0,
        window_start=now - timedelta(hours=6),
        window_end=now,
    )

    assert normalized == 60000.0


def test_fetch_health_payloads_stops_at_first_day_with_data():
    # Adapter should stop at the first day window that yields any metrics and
    # should not continue probing older windows.
    responses = [
        {
            'bucket': [
                {
                    'dataset': [
                        {
                            'dataSourceId': 'derived:com.google.step_count.delta:com.google.android.gms:aggregated',
                            'dataTypeName': 'com.google.step_count.delta',
                            'point': [{'value': [{'intVal': 401}]}],
                        },
                        {
                            'dataSourceId': 'derived:com.google.heart_rate.summary:com.google.android.gms:aggregated',
                            'dataTypeName': 'com.google.heart_rate.summary',
                            'point': [],
                        },
                        {
                            'dataSourceId': 'derived:com.google.body.temperature.summary:com.google.android.gms:aggregated',
                            'dataTypeName': 'com.google.body.temperature.summary',
                            'point': [],
                        },
                        {
                            'dataSourceId': 'derived:com.google.sleep.segment:com.google.android.gms:merged',
                            'dataTypeName': 'com.google.sleep.segment',
                            'point': [],
                        },
                        {
                            'dataSourceId': 'derived:com.google.blood_pressure.summary:com.google.android.gms:aggregated',
                            'dataTypeName': 'com.google.blood_pressure.summary',
                            'point': [],
                        },
                        {
                            'dataSourceId': 'derived:com.google.blood_glucose.summary:com.google.android.gms:aggregated',
                            'dataTypeName': 'com.google.blood_glucose.summary',
                            'point': [],
                        },
                    ]
                }
            ]
        },
        {
            'bucket': [
                {
                    'dataset': [
                        {
                            'dataSourceId': 'derived:com.google.step_count.delta:com.google.android.gms:aggregated',
                            'dataTypeName': 'com.google.step_count.delta',
                            'point': [{'value': [{'intVal': 99999}]}],
                        },
                    ]
                }
            ]
        },
    ]

    adapter = SequenceGoogleFitAdapter(responses)
    context = FetchContext(
        user_id=1,
        provider='google_fit',
        token=TokenBundle(access_token='token', refresh_token='rt'),
        since=None,
    )

    payloads = adapter.fetch_health_payloads(context)

    assert len(payloads) == 1
    payload = payloads[0]
    assert payload.steps == 401
    assert payload.heart_rate is None
    assert payload.temperature is None
    assert payload.sleep_hours is None
    assert payload.blood_pressure is None
    assert payload.sugar is None

    # First attempt asks all canonical families and stops after that day succeeds.
    assert adapter.seen_aggregate_by[0] == [
        'com.google.step_count.delta',
        'com.google.heart_rate.bpm',
        'com.google.body.temperature',
        'com.google.sleep.segment',
        'com.google.blood_pressure',
        'com.google.blood_glucose',
    ]
    assert len(adapter.seen_aggregate_by) == 1

    assert payload.raw_payload is not None
    assert payload.raw_payload['selected_window'] == 'today'
    assert payload.raw_payload['missing_metrics'] == [
        'heart_rate',
        'temperature',
        'sleep_hours',
        'blood_pressure',
        'sugar',
    ]
