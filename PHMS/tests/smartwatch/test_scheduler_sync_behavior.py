from types import SimpleNamespace

from jobs import smartwatch_tasks


def test_sync_scheduler_job_continues_when_one_account_fails(monkeypatch):
    accounts = [
        SimpleNamespace(user_id=1, provider='google_fit'),
        SimpleNamespace(user_id=2, provider='google_fit'),
        SimpleNamespace(user_id=3, provider='google_fit'),
    ]

    monkeypatch.setattr(
        smartwatch_tasks.SmartwatchRepository,
        'get_all_connected_accounts',
        staticmethod(lambda: accounts),
    )

    def fake_trigger_sync(user_id, provider, cursor=None, since=None):
        if user_id == 1:
            return {
                'success': True,
                'message': 'Sync completed (succeeded after 1 retry)',
                'sync_result': {'fetched_count': 5},
            }
        if user_id == 2:
            return {
                'success': False,
                'message': 'Sync failed after 2 retries. Provider timeout.',
            }
        raise RuntimeError('Upstream provider unavailable')

    monkeypatch.setattr(smartwatch_tasks, 'trigger_sync', fake_trigger_sync)

    result = smartwatch_tasks.sync_all_connected_smartwatches()

    assert result['status'] == 'partial_failure'
    assert result['synced_count'] == 1
    assert result['failed_count'] == 2
    assert result['total_accounts'] == 3
    assert result['retry_attempts'] == 2
    assert isinstance(result['errors'], list)
    assert len(result['errors']) == 2
    assert any(item['user_id'] == 2 for item in result['errors'])
    assert any(item['user_id'] == 3 for item in result['errors'])


def test_sync_scheduler_job_no_accounts_returns_success(monkeypatch):
    monkeypatch.setattr(
        smartwatch_tasks.SmartwatchRepository,
        'get_all_connected_accounts',
        staticmethod(lambda: []),
    )

    result = smartwatch_tasks.sync_all_connected_smartwatches()

    assert result['status'] == 'success'
    assert result['message'] == 'No connected accounts'
    assert result['synced_count'] == 0
    assert result['failed_count'] == 0
    assert result['total_accounts'] == 0
    assert result['retry_attempts'] == 0
