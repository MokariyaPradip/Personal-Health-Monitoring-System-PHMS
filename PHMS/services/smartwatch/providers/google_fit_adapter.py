from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from services.smartwatch.contracts import FetchContext, NormalizedHealthPayload, TokenBundle
from services.smartwatch.providers.base import SmartwatchProviderAdapter

logger = logging.getLogger(__name__)


class GoogleFitAdapter(SmartwatchProviderAdapter):
    """Google Fit adapter implementation scaffold.

    Provider-specific OAuth and fetch logic is isolated in this class.
    The output stays canonical for the shared health ingestion pipeline.
    """

    provider_name = 'google_fit'

    _auth_url = 'https://accounts.google.com/o/oauth2/v2/auth'
    _token_url = 'https://oauth2.googleapis.com/token'
    _aggregate_url = 'https://www.googleapis.com/fitness/v1/users/me/dataset:aggregate'

    _scope_list = [
        'https://www.googleapis.com/auth/fitness.activity.read',
        'https://www.googleapis.com/auth/fitness.heart_rate.read',
        'https://www.googleapis.com/auth/fitness.body.read',
        'https://www.googleapis.com/auth/fitness.blood_pressure.read',
        'https://www.googleapis.com/auth/fitness.blood_glucose.read',
        'https://www.googleapis.com/auth/fitness.sleep.read',
    ]

    _data_source_to_field = {
        'com.google.step_count.delta': 'steps',
        'com.google.heart_rate.bpm': 'heart_rate',
        'com.google.body.temperature': 'temperature',
        'com.google.blood_pressure': 'blood_pressure',
        'com.google.blood_glucose': 'sugar',
        'com.google.sleep.segment': 'sleep_hours',
    }

    def __init__(self, client_id: str | None = None, client_secret: str | None = None) -> None:
        self._client_id = client_id or os.getenv('GOOGLE_FIT_CLIENT_ID')
        self._client_secret = client_secret or os.getenv('GOOGLE_FIT_CLIENT_SECRET')

    def _assert_oauth_configured(self) -> None:
        if not self._client_id or not self._client_secret:
            raise ValueError('Google Fit OAuth credentials are not configured')

    def build_authorization_url(self, user_id: int, redirect_uri: str, state: str) -> str:
        self._assert_oauth_configured()
        params = {
            'client_id': self._client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': ' '.join(self._scope_list),
            'access_type': 'offline',
            'include_granted_scopes': 'true',
            'prompt': 'consent',
            'state': f'{state}:{user_id}',
        }
        return f'{self._auth_url}?{urlencode(params)}'

    def _post_form(self, url: str, form_data: dict[str, str]) -> dict:
        body = urlencode(form_data).encode('utf-8')
        request = Request(
            url,
            data=body,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST',
        )
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))

    @staticmethod
    def _parse_expires_at(expires_in: int | str | None) -> datetime | None:
        if expires_in in (None, ''):
            return None
        return datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

    def _to_token_bundle(self, token_payload: dict) -> TokenBundle:
        access_token = token_payload.get('access_token')
        if not access_token:
            raise ValueError('Google Fit token response is missing access_token')

        return TokenBundle(
            access_token=access_token,
            refresh_token=token_payload.get('refresh_token'),
            expires_at=self._parse_expires_at(token_payload.get('expires_in')),
            scope=token_payload.get('scope'),
            provider_user_id=None,
        )

    def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> TokenBundle:
        self._assert_oauth_configured()
        payload = self._post_form(
            self._token_url,
            {
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri,
            },
        )
        return self._to_token_bundle(payload)

    def refresh_access_token(self, refresh_token: str) -> TokenBundle:
        self._assert_oauth_configured()
        payload = self._post_form(
            self._token_url,
            {
                'client_id': self._client_id,
                'client_secret': self._client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
            },
        )
        token_bundle = self._to_token_bundle(payload)
        if token_bundle.refresh_token is None:
            token_bundle.refresh_token = refresh_token
        return token_bundle

    def _post_json(self, url: str, bearer_token: str, payload: dict) -> dict:
        body = json.dumps(payload).encode('utf-8')
        request = Request(
            url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {bearer_token}',
            },
            method='POST',
        )
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))

    @staticmethod
    def _to_ns(dt: datetime) -> int:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1_000_000_000)

    def _build_aggregate_request(self, since: datetime | None) -> tuple[dict, datetime, datetime]:
        end_time = datetime.now(timezone.utc)
        start_time = since or (end_time - timedelta(hours=24))

        aggregate_by = [
            {'dataTypeName': data_type}
            for data_type in self._data_source_to_field
        ]

        request_payload = {
            'startTimeMillis': int(start_time.timestamp() * 1000),
            'endTimeMillis': int(end_time.timestamp() * 1000),
            'aggregateBy': aggregate_by,
            'bucketByTime': {'durationMillis': int((end_time - start_time).total_seconds() * 1000)},
        }
        return request_payload, start_time, end_time

    @staticmethod
    def _extract_numeric_values(point: dict) -> list[float]:
        extracted = []
        for value in point.get('value', []):
            if 'fpVal' in value:
                extracted.append(float(value['fpVal']))
            elif 'intVal' in value:
                extracted.append(float(value['intVal']))
        return extracted

    def _extract_metrics(self, aggregate_response: dict) -> dict[str, float]:
        collected: dict[str, list[float]] = {
            'steps': [],
            'heart_rate': [],
            'temperature': [],
            'blood_pressure': [],
            'sugar': [],
            'sleep_hours': [],
        }

        for bucket in aggregate_response.get('bucket', []):
            for dataset in bucket.get('dataset', []):
                data_source_id = dataset.get('dataSourceId', '')
                target_field = None
                for data_type, mapped_field in self._data_source_to_field.items():
                    if data_type in data_source_id:
                        target_field = mapped_field
                        break
                if not target_field:
                    continue

                for point in dataset.get('point', []):
                    numbers = self._extract_numeric_values(point)
                    if not numbers:
                        continue

                    if target_field == 'sleep_hours':
                        start_ns = int(point.get('startTimeNanos', 0))
                        end_ns = int(point.get('endTimeNanos', 0))
                        if end_ns > start_ns:
                            collected['sleep_hours'].append((end_ns - start_ns) / 3_600_000_000_000)
                        continue

                    if target_field == 'steps':
                        collected['steps'].append(sum(numbers))
                        continue

                    collected[target_field].append(sum(numbers) / len(numbers))

        metrics: dict[str, float] = {}
        if collected['steps']:
            metrics['steps'] = float(sum(collected['steps']))
        for field in ('heart_rate', 'temperature', 'blood_pressure', 'sugar', 'sleep_hours'):
            if collected[field]:
                metrics[field] = float(sum(collected[field]) / len(collected[field]))
        return metrics

    @staticmethod
    def _to_normalized_payload(
        metrics: dict[str, float],
        observed_at: datetime,
        provider: str,
        source_record_id: str,
        raw_payload: dict,
    ) -> NormalizedHealthPayload:
        return NormalizedHealthPayload(
            heart_rate=int(round(metrics['heart_rate'])) if 'heart_rate' in metrics else None,
            temperature=round(metrics['temperature'], 2) if 'temperature' in metrics else None,
            steps=int(round(metrics['steps'])) if 'steps' in metrics else None,
            sleep_hours=round(metrics['sleep_hours'], 2) if 'sleep_hours' in metrics else None,
            blood_pressure=round(metrics['blood_pressure'], 2) if 'blood_pressure' in metrics else None,
            sugar=round(metrics['sugar'], 2) if 'sugar' in metrics else None,
            observed_at=observed_at,
            source_record_id=source_record_id,
            provider=provider,
            raw_payload=raw_payload,
        )

    def fetch_health_payloads(self, context: FetchContext) -> list[NormalizedHealthPayload]:
        since = context.since
        if context.cursor and not since:
            try:
                since = datetime.fromisoformat(context.cursor)
            except ValueError:
                logger.warning('Invalid Google Fit cursor format, falling back to default window')

        aggregate_request, start_time, end_time = self._build_aggregate_request(since)
        aggregate_response = self._post_json(
            self._aggregate_url,
            bearer_token=context.token.access_token,
            payload=aggregate_request,
        )

        metrics = self._extract_metrics(aggregate_response)
        if not metrics:
            logger.info('No Google Fit metrics found for user_id=%s in requested window', context.user_id)
            return []

        source_record_id = f'aggregate:{self._to_ns(start_time)}:{self._to_ns(end_time)}'
        payload = self._to_normalized_payload(
            metrics=metrics,
            observed_at=end_time,
            provider=self.provider_name,
            source_record_id=source_record_id,
            raw_payload=aggregate_response,
        )
        return [payload]
