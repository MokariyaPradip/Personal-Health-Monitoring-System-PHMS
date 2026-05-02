from __future__ import annotations

import json
import logging
import os
import re
import math
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
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
        'https://www.googleapis.com/auth/fitness.body_temperature.read',
        'https://www.googleapis.com/auth/fitness.blood_pressure.read',
        'https://www.googleapis.com/auth/fitness.blood_glucose.read',
        'https://www.googleapis.com/auth/fitness.sleep.read',
    ]

    # Request only canonical aggregate data types supported by Google Fit API.
    _aggregate_data_types = [
        'com.google.step_count.delta',
        'com.google.heart_rate.bpm',
        'com.google.body.temperature',
        'com.google.blood_pressure',
        'com.google.blood_glucose',
        'com.google.sleep.segment',
    ]

    _field_to_data_type = {
        'steps': 'com.google.step_count.delta',
        'heart_rate': 'com.google.heart_rate.bpm',
        'temperature': 'com.google.body.temperature',
        'sleep_hours': 'com.google.sleep.segment',
        'blood_pressure': 'com.google.blood_pressure',
        'sugar': 'com.google.blood_glucose',
    }

    _required_metric_fields = (
        'steps',
        'heart_rate',
        'temperature',
        'sleep_hours',
        'blood_pressure',
        'sugar',
    )

    _max_steps_per_entry = 60000.0

    # Fetch strategy is constrained to recent fixed day windows to avoid
    # cumulative cross-day aggregates in single-entry ingestion.
    _recent_day_window_count = 3

    _data_source_to_field = {
        'com.google.step_count.delta': 'steps',
        'com.google.heart_rate.bpm': 'heart_rate',
        'com.google.heart_rate.summary': 'heart_rate',
        'com.google.body.temperature': 'temperature',
        'com.google.body.temperature.summary': 'temperature',
        'com.google.blood_pressure': 'blood_pressure',
        'com.google.blood_pressure.summary': 'blood_pressure',
        'com.google.blood_glucose': 'sugar',
        'com.google.blood_glucose.summary': 'sugar',
        'com.google.sleep.segment': 'sleep_hours',
    }

    _denied_data_type_pattern = re.compile(r'Cannot read data of type\s+([\w\.]+)', re.IGNORECASE)
    _missing_datasource_pattern = re.compile(r'no default datasource found for:\s*([\w\.]+)', re.IGNORECASE)

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
        # Keep token expiry aligned with project-local naive timestamps.
        return datetime.now() + timedelta(seconds=int(expires_in))

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
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as e:
            raw_body = ''
            try:
                if e.fp is not None:
                    raw_body = e.read().decode('utf-8', errors='replace')
            except Exception:
                raw_body = ''

            error_message = f'HTTP Error {e.code}'
            if raw_body:
                try:
                    body_json = json.loads(raw_body)
                    error_obj = body_json.get('error', {})
                    if isinstance(error_obj, dict):
                        detail = error_obj.get('message') or error_obj.get('status')
                        if detail:
                            error_message = f'{error_message}: {detail}'
                    elif isinstance(error_obj, str):
                        error_message = f'{error_message}: {error_obj}'
                except (TypeError, ValueError):
                    error_message = f'{error_message}: {raw_body[:200]}'

            # Auth/scope denial should surface as actionable re-connect guidance.
            if e.code in (401, 403):
                raise ValueError(
                    f'Google Fit authorization failed ({e.code}). Please disconnect and reconnect '
                    f'the provider to re-grant required permissions. {error_message}'
                ) from e

            raise RuntimeError(f'Google Fit API request failed. {error_message}') from e
        except URLError as e:
            raise ConnectionError(f'Google Fit request failed due to network error: {e.reason}') from e

    @staticmethod
    def _to_ns(dt: datetime) -> int:
        if dt.tzinfo is None:
            local_timezone = datetime.now().astimezone().tzinfo
            dt = dt.replace(tzinfo=local_timezone)
        return int(dt.timestamp() * 1_000_000_000)

    @staticmethod
    def _as_local_aware(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return dt.astimezone()

    def _build_aggregate_request(
        self,
        start_time: datetime,
        end_time: datetime,
        data_types: list[str] | None = None,
    ) -> tuple[dict, datetime, datetime]:
        start_time = self._as_local_aware(start_time)
        end_time = self._as_local_aware(end_time)

        selected_types = data_types or list(self._aggregate_data_types)

        aggregate_by = [
            {'dataTypeName': data_type}
            for data_type in selected_types
        ]

        request_payload = {
            'startTimeMillis': int(start_time.timestamp() * 1000),
            'endTimeMillis': int(end_time.timestamp() * 1000),
            'aggregateBy': aggregate_by,
            'bucketByTime': {'durationMillis': int((end_time - start_time).total_seconds() * 1000)},
        }
        return request_payload, start_time, end_time

    def _recent_daily_windows(self) -> list[tuple[str, datetime, datetime]]:
        """Return fixed day windows: today, yesterday, day-before-yesterday."""
        now = datetime.now().astimezone()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        windows: list[tuple[str, datetime, datetime]] = [
            ('today', today_start, now),
        ]

        for day_offset in (1, 2):
            day_start = today_start - timedelta(days=day_offset)
            day_end = today_start - timedelta(days=day_offset - 1)
            label = 'yesterday' if day_offset == 1 else 'day-before-yesterday'
            windows.append((label, day_start, day_end))

        return windows

    @staticmethod
    def _all_required_metrics_present(metrics: dict[str, float]) -> bool:
        return all(field in metrics for field in GoogleFitAdapter._required_metric_fields)

    @staticmethod
    def _missing_required_metrics(metrics: dict[str, float]) -> list[str]:
        return [
            field
            for field in GoogleFitAdapter._required_metric_fields
            if field not in metrics
        ]

    def _data_types_for_missing_metrics(self, missing_metrics: list[str]) -> list[str]:
        selected_data_types = [
            self._field_to_data_type[field]
            for field in missing_metrics
            if field in self._field_to_data_type
        ]
        if not selected_data_types:
            return list(self._aggregate_data_types)
        return selected_data_types

    @staticmethod
    def _collect_dataset_refs_with_points(aggregate_response: dict) -> list[tuple[str, int]]:
        refs_with_points: list[tuple[str, int]] = []
        for bucket in aggregate_response.get('bucket', []):
            for dataset in bucket.get('dataset', []):
                data_source_id = dataset.get('dataSourceId', '')
                data_type_name = dataset.get('dataTypeName', '')
                ref = data_source_id or data_type_name
                if not ref:
                    continue
                refs_with_points.append((ref, len(dataset.get('point', []))))
        return refs_with_points

    def _extract_denied_data_type(self, error_message: str) -> str | None:
        match = self._denied_data_type_pattern.search(error_message)
        if not match:
            return None
        return match.group(1).strip()

    def _extract_missing_datasource_type(self, error_message: str) -> str | None:
        match = self._missing_datasource_pattern.search(error_message)
        if not match:
            return None
        return match.group(1).strip()

    @staticmethod
    def _extract_map_numeric_entries(point: dict) -> list[tuple[str, float]]:
        entries: list[tuple[str, float]] = []

        def walk_map(map_items: list[dict]) -> None:
            for map_item in map_items:
                key = str(map_item.get('key', '')).lower()
                value = map_item.get('value', {})

                if isinstance(value, dict):
                    if 'fpVal' in value:
                        entries.append((key, float(value['fpVal'])))
                    elif 'intVal' in value:
                        entries.append((key, float(value['intVal'])))

                nested_items = value.get('mapVal', []) if isinstance(value, dict) else []
                if isinstance(nested_items, list) and nested_items:
                    walk_map(nested_items)

        for value in point.get('value', []):
            map_items = value.get('mapVal', []) if isinstance(value, dict) else []
            if isinstance(map_items, list) and map_items:
                walk_map(map_items)

        return entries

    @staticmethod
    def _pick_map_value(entries: list[tuple[str, float]], key_hints: tuple[str, ...]) -> float | None:
        for key_hint in key_hints:
            for key, numeric in entries:
                if key_hint in key:
                    return numeric
        return None

    @staticmethod
    def _extract_numeric_values(point: dict) -> list[float]:
        extracted: list[float] = []

        def walk(node):
            if isinstance(node, dict):
                if 'fpVal' in node:
                    extracted.append(float(node['fpVal']))
                if 'intVal' in node:
                    extracted.append(float(node['intVal']))
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(point.get('value', []))
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

        dataset_extraction_summary: dict[str, dict] = {}

        for bucket in aggregate_response.get('bucket', []):
            for dataset in bucket.get('dataset', []):
                data_source_id = dataset.get('dataSourceId', '')
                data_type_name = dataset.get('dataTypeName', '')
                target_field = self._resolve_target_field(data_source_id, data_type_name)
                
                if not target_field:
                    logger.debug(
                        'No mapping found for data source: %s | data type: %s',
                        data_source_id, data_type_name
                    )
                    continue

                point_count = len(dataset.get('point', []))
                dataset_extraction_summary[target_field] = {
                    'data_source': data_source_id,
                    'points_found': point_count,
                    'extracted': 0,
                }

                for point in dataset.get('point', []):
                    if target_field == 'sleep_hours':
                        start_ns = int(point.get('startTimeNanos', 0))
                        end_ns = int(point.get('endTimeNanos', 0))
                        if end_ns > start_ns:
                            collected['sleep_hours'].append((end_ns - start_ns) / 3_600_000_000_000)
                            dataset_extraction_summary[target_field]['extracted'] += 1
                        continue

                    map_entries = self._extract_map_numeric_entries(point)

                    if target_field == 'blood_pressure':
                        systolic = self._pick_map_value(
                            map_entries,
                            (
                                'blood_pressure_systolic',
                                'systolic',
                                'systolic_average',
                                'avg_systolic',
                            ),
                        )
                        if systolic is None and map_entries:
                            # Use the highest pressure-like value as a practical fallback for systolic.
                            systolic = max(numeric for _, numeric in map_entries)
                        if systolic is not None:
                            collected['blood_pressure'].append(systolic)
                            dataset_extraction_summary[target_field]['extracted'] += 1
                            continue

                    if target_field == 'sugar':
                        glucose = self._pick_map_value(
                            map_entries,
                            (
                                'blood_glucose_level',
                                'glucose',
                                'level',
                                'average',
                                'avg',
                                'mean',
                            ),
                        )
                        if glucose is None and map_entries:
                            glucose = map_entries[0][1]
                        if glucose is not None:
                            collected['sugar'].append(glucose)
                            dataset_extraction_summary[target_field]['extracted'] += 1
                            continue

                    if target_field == 'heart_rate' and map_entries:
                        heart_rate = self._pick_map_value(
                            map_entries,
                            ('average', 'avg', 'mean', 'bpm', 'resting'),
                        )
                        if heart_rate is None:
                            heart_rate = map_entries[0][1]
                        collected['heart_rate'].append(heart_rate)
                        dataset_extraction_summary[target_field]['extracted'] += 1
                        continue

                    if target_field == 'temperature' and map_entries:
                        temperature = self._pick_map_value(
                            map_entries,
                            ('average', 'avg', 'mean', 'temperature', 'body_temperature'),
                        )
                        if temperature is None:
                            temperature = map_entries[0][1]
                        collected['temperature'].append(temperature)
                        dataset_extraction_summary[target_field]['extracted'] += 1
                        continue

                    numbers = self._extract_numeric_values(point)
                    if not numbers:
                        continue

                    if target_field == 'steps':
                        collected['steps'].append(sum(numbers))
                        dataset_extraction_summary[target_field]['extracted'] += 1
                        continue

                    collected[target_field].append(sum(numbers) / len(numbers))
                    dataset_extraction_summary[target_field]['extracted'] += 1

        # Log extraction summary for diagnostics. Promote failed extraction to warning.
        for field, summary in dataset_extraction_summary.items():
            if summary['points_found'] > 0 and summary['extracted'] == 0:
                logger.warning(
                    'Google Fit parsing did not extract %s despite %d points from source=%s',
                    field,
                    summary['points_found'],
                    summary['data_source'],
                )
            else:
                logger.debug(
                    'Field %s: source=%s, found %d points, extracted from %d points',
                    field, summary['data_source'], summary['points_found'], summary['extracted']
                )

        metrics: dict[str, float] = {}
        if collected['steps']:
            metrics['steps'] = float(sum(collected['steps']))
        for field in ('heart_rate', 'temperature', 'blood_pressure', 'sugar'):
            if collected[field]:
                metrics[field] = float(sum(collected[field]) / len(collected[field]))
        if collected['sleep_hours']:
            # Sleep segments represent duration slices and should be summed.
            metrics['sleep_hours'] = float(sum(collected['sleep_hours']))
        return metrics

    def _normalize_steps_for_ingestion(
        self,
        *,
        steps: float | None,
        window_start: datetime | None,
        window_end: datetime | None,
    ) -> float | None:
        """Normalize oversized step totals from long aggregate windows.

        Google Fit aggregate responses can return step totals covering the full
        requested range. PHMS persists one record per sync payload with schema
        limit steps <= 60,000, so multi-day totals should be converted to a
        per-day estimate before ingestion.
        """
        if steps is None:
            return None

        normalized_steps = float(steps)

        if (
            normalized_steps > self._max_steps_per_entry
            and window_start is not None
            and window_end is not None
        ):
            window_seconds = max((window_end - window_start).total_seconds(), 0.0)
            window_days = max(1.0, math.ceil(window_seconds / 86_400.0))

            if window_days > 1.0:
                per_day_estimate = normalized_steps / window_days
                logger.warning(
                    'Google Fit steps exceeded per-entry max for user window; '
                    'normalizing cumulative steps %.2f across %.0f days to %.2f/day',
                    normalized_steps,
                    window_days,
                    per_day_estimate,
                )
                normalized_steps = per_day_estimate

        if normalized_steps > self._max_steps_per_entry:
            logger.warning(
                'Google Fit steps still above schema max after normalization (%.2f); capping to %.0f',
                normalized_steps,
                self._max_steps_per_entry,
            )
            normalized_steps = self._max_steps_per_entry

        if normalized_steps < 0:
            normalized_steps = 0.0

        return normalized_steps

    def _resolve_target_field(self, data_source_id: str, data_type_name: str) -> str | None:
        data_type_reference = f'{data_source_id} {data_type_name}'
        for data_type, mapped_field in self._data_source_to_field.items():
            if data_type in data_type_reference:
                return mapped_field
        return None

    def _empty_metric_point_totals(self) -> dict[str, int]:
        return {field: 0 for field in self._required_metric_fields}

    def _extract_metric_point_totals(self, aggregate_response: dict) -> dict[str, int]:
        totals = self._empty_metric_point_totals()

        for bucket in aggregate_response.get('bucket', []):
            for dataset in bucket.get('dataset', []):
                data_source_id = dataset.get('dataSourceId', '')
                data_type_name = dataset.get('dataTypeName', '')
                target_field = self._resolve_target_field(data_source_id, data_type_name)
                if target_field is None:
                    continue
                totals[target_field] += len(dataset.get('point', []))

        return totals

    def _diagnostics_from_point_totals(self, metric_point_totals: dict[str, int]) -> dict[str, Any]:
        non_zero_families = [
            field for field in self._required_metric_fields if metric_point_totals.get(field, 0) > 0
        ]
        zero_point_families = [
            field for field in self._required_metric_fields if metric_point_totals.get(field, 0) == 0
        ]
        return {
            'metric_point_totals': metric_point_totals,
            'non_zero_metric_families': non_zero_families,
            'zero_point_metric_families': zero_point_families,
        }

    @staticmethod
    def _resolve_since_from_context(context: FetchContext) -> datetime | None:
        since = context.since
        if context.cursor and not since:
            try:
                since = datetime.fromisoformat(context.cursor)
            except ValueError:
                logger.warning('Invalid Google Fit cursor format, falling back to default window')
        return since

    def get_pre_sync_diagnostics(self, context: FetchContext) -> dict[str, Any]:
        metric_point_totals = self._empty_metric_point_totals()
        sampled_dataset_refs: list[tuple[str, int]] = []
        selected_window_label = 'none'
        selected_window_start = None
        selected_window_end = None

        for window_label, window_start, window_end in self._recent_daily_windows():
            aggregate_request, _start_time, _end_time = self._build_aggregate_request(window_start, window_end)
            aggregate_response = self._post_json(
                self._aggregate_url,
                bearer_token=context.token.access_token,
                payload=aggregate_request,
            )

            refs_with_points = self._collect_dataset_refs_with_points(aggregate_response)
            sampled_dataset_refs.extend(refs_with_points)

            extracted_totals = self._extract_metric_point_totals(aggregate_response)
            if sum(extracted_totals.values()) > 0:
                metric_point_totals = extracted_totals
                selected_window_label = window_label
                selected_window_start = _start_time
                selected_window_end = _end_time
                break

        diagnostics = self._diagnostics_from_point_totals(metric_point_totals)
        diagnostics['window_label'] = selected_window_label
        diagnostics['window_start'] = selected_window_start.isoformat() if selected_window_start else None
        diagnostics['window_end'] = selected_window_end.isoformat() if selected_window_end else None
        diagnostics['dataset_refs'] = [
            {'ref': ref, 'points': points}
            for ref, points in sorted(set(sampled_dataset_refs), key=lambda item: item[0])
        ]

        logger.warning(
            'Google Fit pre-sync diagnostics for user_id=%s: non_zero_metric_families=%s, point_totals=%s',
            context.user_id,
            diagnostics['non_zero_metric_families'],
            diagnostics['metric_point_totals'],
        )

        return diagnostics

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
        selected_metrics: dict[str, float] | None = None
        selected_start_time: datetime | None = None
        selected_end_time: datetime | None = None
        selected_window_label: str | None = None
        selected_aggregate_response: dict | None = None
        selected_metric_point_totals: dict[str, int] = self._empty_metric_point_totals()

        for window_label, window_start, window_end in self._recent_daily_windows():
            requested_data_types = list(self._aggregate_data_types)

            logger.warning(
                'Google Fit fetch attempt for user_id=%s: day_window=%s, requested_data_types=%s',
                context.user_id,
                window_label,
                requested_data_types,
            )

            aggregate_response = None
            start_time = None
            end_time = None

            while requested_data_types:
                aggregate_request, start_time, end_time = self._build_aggregate_request(
                    window_start,
                    window_end,
                    data_types=requested_data_types,
                )
                try:
                    aggregate_response = self._post_json(
                        self._aggregate_url,
                        bearer_token=context.token.access_token,
                        payload=aggregate_request,
                    )
                    break
                except ValueError as e:
                    denied_data_type = self._extract_denied_data_type(str(e))
                    if denied_data_type and denied_data_type in requested_data_types:
                        logger.warning(
                            'Google Fit denied data type %s for user_id=%s; retrying without it.',
                            denied_data_type,
                            context.user_id,
                        )
                        requested_data_types = [
                            data_type for data_type in requested_data_types if data_type != denied_data_type
                        ]
                        continue
                    raise
                except RuntimeError as e:
                    missing_type = self._extract_missing_datasource_type(str(e))
                    if missing_type and missing_type in requested_data_types:
                        logger.warning(
                            'Google Fit has no default datasource for %s (user_id=%s); retrying without it.',
                            missing_type,
                            context.user_id,
                        )
                        requested_data_types = [
                            data_type for data_type in requested_data_types if data_type != missing_type
                        ]
                        continue
                    raise

            if aggregate_response is None or start_time is None or end_time is None:
                raise ValueError(
                    'Google Fit denied access to all configured data types. '
                    'Please reconnect and grant at least one health scope.'
                )

            refs_with_points = self._collect_dataset_refs_with_points(aggregate_response)
            if refs_with_points:
                refs_text = ', '.join(
                    f'{ref} (points={points})'
                    for ref, points in sorted(set(refs_with_points), key=lambda item: item[0])
                )
                logger.warning(
                    'Google Fit dataset refs for user_id=%s (%s): %s',
                    context.user_id,
                    window_label,
                    refs_text,
                )
            else:
                logger.warning(
                    'Google Fit dataset refs for user_id=%s (%s): none',
                    context.user_id,
                    window_label,
                )

            extracted_totals = self._extract_metric_point_totals(aggregate_response)
            extracted_metrics = self._extract_metrics(aggregate_response)

            logger.warning(
                'Google Fit day-window status for user_id=%s (%s): found=%s, missing=%s',
                context.user_id,
                window_label,
                sorted(list(extracted_metrics.keys())),
                self._missing_required_metrics(extracted_metrics),
            )

            if extracted_metrics:
                selected_metrics = extracted_metrics
                selected_start_time = start_time
                selected_end_time = end_time
                selected_window_label = window_label
                selected_aggregate_response = aggregate_response
                selected_metric_point_totals = extracted_totals
                break

        if not selected_metrics:
            logger.info('No Google Fit metrics found for user_id=%s in requested window', context.user_id)
            return []

        missing_fields = [field for field in self._required_metric_fields if field not in selected_metrics]
        if missing_fields:
            logger.warning(
                'Google Fit metrics missing for user_id=%s in selected day window (%s): %s',
                context.user_id,
                selected_window_label,
                ', '.join(missing_fields),
            )

        point_diagnostics = self._diagnostics_from_point_totals(selected_metric_point_totals)
        logger.warning(
            'Google Fit pre-ingestion metric families for user_id=%s: non_zero=%s, zero=%s, point_totals=%s',
            context.user_id,
            point_diagnostics['non_zero_metric_families'],
            point_diagnostics['zero_point_metric_families'],
            point_diagnostics['metric_point_totals'],
        )

        logger.warning('Google Fit extracted metrics for user_id=%s: %s', context.user_id, selected_metrics)

        source_start = selected_start_time or datetime.now().astimezone()
        source_end = selected_end_time or datetime.now().astimezone()

        normalized_steps = self._normalize_steps_for_ingestion(
            steps=selected_metrics.get('steps'),
            window_start=source_start,
            window_end=source_end,
        )
        if normalized_steps is not None:
            selected_metrics['steps'] = normalized_steps

        logger.warning(
            'Google Fit final metrics before payload for user_id=%s: selected_day=%s, metrics=%s, missing=%s',
            context.user_id,
            selected_window_label,
            selected_metrics,
            missing_fields,
        )

        source_record_id = f'aggregate:{self._to_ns(source_start)}:{self._to_ns(source_end)}'
        payload = self._to_normalized_payload(
            metrics=selected_metrics,
            observed_at=source_end.replace(tzinfo=None),
            provider=self.provider_name,
            source_record_id=source_record_id,
            raw_payload={
                'selected_window': selected_window_label,
                'selected_window_payload': selected_aggregate_response,
                'metric_point_totals': point_diagnostics['metric_point_totals'],
                'non_zero_metric_families': point_diagnostics['non_zero_metric_families'],
                'zero_point_metric_families': point_diagnostics['zero_point_metric_families'],
                'missing_metrics': missing_fields,
            },
        )
        return [payload]
