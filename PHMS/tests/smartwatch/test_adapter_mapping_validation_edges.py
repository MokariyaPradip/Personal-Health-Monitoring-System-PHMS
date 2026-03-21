from datetime import datetime, timezone

import pytest

from services.smartwatch.contracts import FetchContext, TokenBundle
from services.smartwatch.providers.google_fit_adapter import GoogleFitAdapter


class EdgeCaseGoogleFitAdapter(GoogleFitAdapter):
    def __init__(self, aggregate_response):
        super().__init__(client_id='client-id', client_secret='client-secret')
        self._aggregate_response = aggregate_response

    def _post_json(self, url, bearer_token, payload):
        return dict(self._aggregate_response)


def test_to_token_bundle_requires_access_token():
    adapter = GoogleFitAdapter(client_id='client-id', client_secret='client-secret')

    with pytest.raises(ValueError, match='access_token'):
        adapter._to_token_bundle({'refresh_token': 'rt'})


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
                ]
            }
        ]
    }

    metrics = adapter._extract_metrics(aggregate_response)

    assert metrics['steps'] == 2000.0
    assert metrics['sleep_hours'] == 1.0
