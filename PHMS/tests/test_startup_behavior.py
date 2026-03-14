def test_app_import_does_not_start_scheduler():
    import app as app_module

    assert hasattr(app_module, 'scheduler')
    assert app_module.scheduler is None


def test_bootstrap_function_exists_for_explicit_startup():
    import app as app_module

    assert hasattr(app_module, 'bootstrap_background_services')
    assert callable(app_module.bootstrap_background_services)
