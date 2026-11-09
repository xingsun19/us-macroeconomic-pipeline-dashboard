"""Verify on-demand execution and cleanup without controlling the user's Docker."""

from pathlib import Path
import json
import os
import shutil
import subprocess
import sys

import pytest


@pytest.fixture
def launcher(tmp_path):
    root = tmp_path / "Project with spaces"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "scripts/run.sh", root / "scripts/run.sh")
    (root / ".env").write_text("FRED_API_KEY=" + "a" * 32 + "\n")
    binary = tmp_path / "bin"
    binary.mkdir()
    fake = f"#!{sys.executable}\n" + '''from pathlib import Path
import json, os, sys
name, args = Path(sys.argv[0]).name, sys.argv[1:]
engine = Path(os.environ['FAKE_ENGINE'])
with open(os.environ['FAKE_EVENTS'], 'a') as log:
    log.write(json.dumps([name, *args]) + '\\n')
if name == 'colima':
    if args == ['start']: engine.touch()
    if args == ['stop']: engine.unlink(missing_ok=True)
elif name == 'docker':
    if args == ['info']: sys.exit(0 if engine.exists() else 1)
    if args == ['context', 'show']: print(os.environ.get('FAKE_CONTEXT', 'colima'))
    if args == ['ps', '-q'] and os.environ.get('FAKE_OTHERS') == '1': print('another-project')
    if args[:2] == ['compose', 'run'] and os.environ.get('FAKE_FAIL') == '1': sys.exit(7)
'''
    for name in ("docker", "colima", "open"):
        path = binary / name
        path.write_text(fake)
        path.chmod(0o755)
    env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"],
           "FAKE_ENGINE": str(tmp_path / "engine"), "FAKE_EVENTS": str(tmp_path / "events")}
    return root, env


def execute(launcher, *, batch=False, ready=True, **flags):
    root, env = launcher
    if ready:
        Path(env["FAKE_ENGINE"]).touch()
    env.update(flags)
    result = subprocess.run(["bash", str(root / "scripts/run.sh"), *(["--batch"] if batch else [])],
                            input="\n", text=True, capture_output=True, env=env, timeout=15)
    event_file = Path(env["FAKE_EVENTS"])
    events = [json.loads(line) for line in event_file.read_text().splitlines()] if event_file.exists() else []
    return result, events


def test_run_opens_dashboard_and_return_stops_services(launcher):
    result, events = execute(launcher)
    assert result.returncode == 0, result.stdout + result.stderr
    run = next(i for i, e in enumerate(events) if e[:3] == ["docker", "compose", "run"])
    dashboard = next(i for i, e in enumerate(events) if e[:3] == ["docker", "compose", "up"] and e[-1] == "dashboard")
    cleanup = max(i for i, e in enumerate(events) if e == ["docker", "compose", "stop", "airflow", "dashboard", "postgres"])
    assert run < dashboard < cleanup
    assert ["colima", "stop"] not in events
    assert not (launcher[0] / "data/.run-lock").exists()


def test_failed_run_returns_failure_and_cleans_up_without_dashboard(launcher):
    result, events = execute(launcher, FAKE_FAIL="1")
    assert result.returncode == 7
    assert not any(e[:3] == ["docker", "compose", "up"] and e[-1] == "dashboard" for e in events)
    assert ["docker", "rm", "-f", "us-macro-manual-run"] in events
    assert not (launcher[0] / "data/.run-lock").exists()


@pytest.mark.parametrize("other_containers", [False, True])
@pytest.mark.parametrize("context", ["colima", "default"])
def test_only_stop_launched_colima_when_no_other_containers(launcher, other_containers, context):
    result, events = execute(launcher, batch=True, ready=False, FAKE_OTHERS=str(int(other_containers)), FAKE_CONTEXT=context)
    assert result.returncode == 0, result.stdout + result.stderr
    assert ["colima", "start"] in events
    assert (["colima", "stop"] in events) is not other_containers
    assert Path(launcher[1]["FAKE_ENGINE"]).exists() is other_containers


def test_duplicate_click_does_not_touch_running_services(launcher):
    root, _ = launcher
    lock = root / "data/.run-lock"
    lock.mkdir(parents=True)
    (lock / "pid").write_text(str(os.getpid()))
    result, events = execute(launcher, batch=True)
    assert result.returncode == 1
    assert "Another Run window" in result.stdout
    assert events == []
    assert lock.exists()
