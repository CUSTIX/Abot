"""Guards for deploy files no unit test exercises: a wrong edit here only shows in production."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "bin" / "seconds_until_hour.py"


def _read(name):
    return (ROOT / name).read_text()


def test_render_health_check_does_not_touch_the_database():
    """/healthz/ runs SELECT 1; polling it all day would keep the free Neon database awake."""
    assert "healthCheckPath: /livez/" in _read("render.yaml")


def test_render_deploys_only_after_ci_passes():
    assert "autoDeployTrigger: checksPass" in _read("render.yaml")


def test_the_demo_resets_every_night():
    assert "DEMO_RESET_HOUR" in _read("render.yaml")


def test_access_log_does_not_record_query_strings():
    script = _read("bin/start.sh")
    assert "--access-logformat" in script and "%(U)s" in script and "%(q)s" not in script


def test_gunicorn_uses_threads_and_recycles_workers():
    script = _read("bin/start.sh")
    assert "--worker-class gthread" in script and "--max-requests" in script


def test_start_script_is_valid_shell():
    script = str(ROOT / "bin" / "start.sh")
    assert subprocess.run(["sh", "-n", script]).returncode == 0  # noqa: S603, S607


def test_the_wipe_only_runs_in_demo_mode():
    assert 'DEMO_MODE:-false}" = "true"' in _read("bin/start.sh")


def test_a_bad_reset_hour_is_reported_not_silently_ignored():
    assert "Nightly demo reset disabled" in _read("bin/start.sh")


def test_keep_awake_pings_the_database_free_endpoint():
    workflow = _read(".github/workflows/keep-awake.yml")
    assert "/livez/" in workflow and "cron:" in workflow


@pytest.mark.parametrize("bad", ["abc", "25", "-1", "4.5", ""])
def test_the_cli_rejects_an_invalid_hour_cleanly(bad):
    result = subprocess.run(  # noqa: S603 - our own script, fixed arguments
        [sys.executable, str(CLI), bad], capture_output=True, text=True
    )
    assert result.returncode != 0 and "Traceback" not in result.stderr
    assert "0-23" in result.stderr


def test_the_cli_prints_whole_seconds_for_a_valid_hour():
    result = subprocess.run(  # noqa: S603 - our own script, fixed arguments
        [sys.executable, str(CLI), "4"], capture_output=True, text=True
    )
    assert result.returncode == 0 and 0 < int(result.stdout) <= 24 * 3600 + 1


def test_next_reset_is_tomorrow_when_the_hour_has_just_passed():
    import datetime as dt

    spec = importlib.util.spec_from_file_location("seconds_until_hour", CLI)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tz = dt.timezone(dt.timedelta(hours=8))
    assert module.seconds_until_hour(4, dt.datetime(2026, 11, 14, 4, 0, tzinfo=tz)) == 86401
    assert module.seconds_until_hour(4, dt.datetime(2026, 11, 14, 3, 0, tzinfo=tz)) == 3601
