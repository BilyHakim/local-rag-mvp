def test_postgres_api_does_not_shadow_service_functions():
    from app.api import postgres as postgres_api
    from app.services import postgres_service

    assert postgres_api.postgres_test_connection is not postgres_service.test_connection
    assert postgres_api.postgres_list_tables is not postgres_service.list_tables
    assert postgres_api.postgres_sync_tables is not postgres_service.sync_tables
