"""Health check, the React shell, security headers and settings parsing."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings import database_from_url

pytestmark = pytest.mark.django_db


def test_health(client):
    response = client.get("/healthz/")
    assert response.status_code == 200 and response.content == b"ok"


def test_security_headers(client):
    response = client.get("/healthz/")
    csp = response["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert response["X-Frame-Options"] == "DENY"
    assert "camera=()" in response["Permissions-Policy"]


def test_signed_in_api_responses_are_not_cached(api):
    assert api.get("/api/today/")["Cache-Control"] == "no-store, private"


def test_client_routes_get_the_react_shell(client, settings, tmp_path):
    (tmp_path / "index.html").write_text("<div id=root></div>")
    settings.FRONTEND_DIST = tmp_path
    for url in ("/", "/wallets", "/plan/bills"):
        response = client.get(url)
        assert response.status_code == 200 and b"id=root" in b"".join(response.streaming_content)
    assert client.get("/api/nope/").status_code == 404


def test_without_a_build_the_root_explains_the_dev_server(client, settings, tmp_path):
    settings.FRONTEND_DIST = tmp_path
    assert b"5173" in client.get("/").content


def test_database_url_parsing():
    db = database_from_url("postgresql://u:p%40ss@host.example:5433/sahod?sslmode=require")
    assert db["PASSWORD"] == "p@ss" and db["PORT"] == "5433"
    assert db["OPTIONS"] == {"connect_timeout": 10, "sslmode": "require"}
    assert db["CONN_MAX_AGE"] == 60 and db["CONN_HEALTH_CHECKS"] is True
    with pytest.raises(ImproperlyConfigured):
        database_from_url("mysql://x")


def test_livez_answers_without_touching_the_database(client, django_assert_num_queries):
    """The uptime heartbeat pings this, so the free database can still suspend when idle."""
    with django_assert_num_queries(0):
        response = client.get("/livez/")
    assert response.status_code == 200 and response.content == b"ok"
