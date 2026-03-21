def test_smartwatch_endpoints_registered(app):
    rules = {rule.endpoint: rule for rule in app.url_map.iter_rules()}

    expected_endpoints = {
        'smartwatch_page',
        'authorize',
        'callback',
        'disconnect',
        'sync_now',
        'status',
    }

    missing = sorted(expected_endpoints - set(rules.keys()))
    assert not missing, f'Missing smartwatch endpoints: {missing}'


def test_smartwatch_routes_have_expected_methods(app):
    routes_by_path = {rule.rule: rule.methods for rule in app.url_map.iter_rules()}

    assert 'GET' in routes_by_path['/smartwatch']
    assert 'GET' in routes_by_path['/smartwatch/integration']
    assert 'GET' in routes_by_path['/smartwatch/authorize/<provider>']
    assert 'GET' in routes_by_path['/smartwatch/callback']
    assert 'POST' in routes_by_path['/smartwatch/disconnect/<provider>']
    assert 'POST' in routes_by_path['/smartwatch/sync-now/<provider>']
    assert 'GET' in routes_by_path['/smartwatch/status/<provider>']
