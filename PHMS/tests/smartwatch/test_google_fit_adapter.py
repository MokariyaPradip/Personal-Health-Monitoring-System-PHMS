from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

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
