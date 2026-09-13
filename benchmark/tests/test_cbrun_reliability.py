"""Regression coverage for operational outcomes, independent of model scores."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest

BENCHMARK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BENCHMARK))

from cbrun.cli import main
from cbrun.docker_env import Container, docker_available, image_exists
from cbrun.limits import Limits
from cbrun.preflight import validate_case
from cbrun.run_case import run_trial
from cbrun.state import atomic_json, digest, file_manifest, image_identity
from coding_bench_harbor._leakage import scan_leakage


def make_case(root: Path, name: str = "case999") -> Path:
    case = root / name
    for directory in ("public", "source", "milestones/final/tests"):
        (case / directory).mkdir(parents=True)
    (case / "public/Full_PRD.md").write_text("# Pipeline fixture\n" + "Implement answer.value() to return 42. " * 12)
    (case / "public/Interface_Contract.md").write_text("# Interface\nProvide a Python module named answer with a value() function returning the integer 42.\n")
    runner = {"language_label": "Python", "install_command": "echo fixture-toolchain-ready",
              "build_command": "", "workdir": ".", "test_command_template": "PYTHONPATH=src python3 -m pytest {test_files}",
              "environment_checks": [{"name": "python", "command": "python3 -c 'import pytest'"}]}
    atomic_json(case / "source/manifest.json", {"schema_version": 3, "case_id": name,
                "status": "released", "sensitive_terms": ["forbidden_upstream"], "runner": runner})
    atomic_json(case / "source/recipe.lock.json", {"schema_version": 1, "base_image": "codingbench-base/ubuntu:24.04", "runner": runner})
    (case / "milestones/final/tests/F01_acceptance.py").write_text("import answer\n\ndef test_answer():\n    assert answer.value() == 42\n")
    atomic_json(case / "milestones/final/test_manifest.json", {
        "schema_version": 1, "step": "final",
        "test_files": ["tests/F01_acceptance.py"], "test_command": "PYTHONPATH=src python3 -m pytest", "workdir": "."})
    return case


def test_every_released_case_passes_default_release_preflight():
    cases = sorted(p for p in (BENCHMARK / "cases").iterdir() if (p / "source/manifest.json").is_file())
    assert cases
    for case in cases:
        assert validate_case(case)["status"] == "ready"


def test_identities_match_boundaries_and_real_qualified_names():
    assert not scan_leakage("readable degradation", ["ada"])
    assert scan_leakage("ada::parse", ["ada"])
    assert scan_leakage("import forbidden_upstream.codec", ["forbidden_upstream"])
    assert scan_leakage("https://github.com/example/source.git", ["github.com/example/source.git"])


def test_new_cases_are_discovered_without_editing_runner(tmp_path):
    make_case(tmp_path / "cases", "case901")
    make_case(tmp_path / "cases", "case902")
    out = tmp_path / "preflight"
    assert main(["--all", "--cases-root", str(tmp_path / "cases"), "--preflight", "--out", str(out)]) == 0
    report = json.loads((out / "preflight.json").read_text())
    assert report["complete"] is True
    assert {x["case_id"] for x in report["cases"]} == {"case901", "case902"}


def test_preflight_does_not_silently_bypass_bad_case_or_missing_policy(tmp_path):
    case = make_case(tmp_path)
    with pytest.raises(ValueError, match="denylist"):
        validate_case(case, require_denylist=True)
    contract = case / "public/Interface_Contract.md"
    contract.write_text(contract.read_text() + "\nforbidden_upstream\n")
    with pytest.raises(Exception, match="source-identity"):
        validate_case(case)
    report = validate_case(case, allow_leakage=True)
    assert report["public_leakage"] == "overridden"


@pytest.mark.parametrize("stdout,stderr", [(b"partial output", None), (b"partial", b"error"), (None, b"\xffbad utf8"), (None, None)])
def test_timeout_output_is_normalized(stdout, stderr, monkeypatch):
    def expired(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", 0.25, output=stdout, stderr=stderr)
    monkeypatch.setattr(subprocess, "run", expired)
    outcome = Container("fixture").exec("sleep 2", timeout_sec=0.25)
    assert outcome.timed_out and outcome.exit_code == 124
    assert isinstance(outcome.tail, str)


def test_output_directory_is_never_overwritten(tmp_path):
    make_case(tmp_path / "cases")
    out = tmp_path / "existing"
    out.mkdir()
    sentinel = out / "summary.json"
    sentinel.write_text("preserved")
    assert main(["--all", "--cases-root", str(tmp_path / "cases"), "--preflight", "--out", str(out)]) == 2
    assert sentinel.read_text() == "preserved"


def test_case_fingerprint_changes_with_content_not_bytecode(tmp_path):
    case = make_case(tmp_path)
    before = digest(file_manifest(case))
    cache = case / "milestones/final/tests/__pycache__"
    cache.mkdir()
    (cache / "generated.pyc").write_bytes(b"cache")
    assert digest(file_manifest(case)) == before
    (case / "public/Interface_Contract.md").write_text("Changed public contract")
    assert digest(file_manifest(case)) != before


@pytest.fixture(scope="module")
def docker_case(tmp_path_factory):
    if not docker_available() or not image_exists("codingbench-base/ubuntu:24.04"):
        pytest.skip("build the shared Docker base to run lifecycle regressions")
    root = tmp_path_factory.mktemp("pipeline-controls")
    name = "control-" + uuid.uuid4().hex[:12]
    case = make_case(root, name)
    yield case, root
    # Remove only image tags belonging to this unique test case.
    for repository in ("codingbench-benchmark", "codingbench-env"):
        proc = subprocess.run(["docker", "image", "ls", "--filter", f"reference={repository}/{name}:*",
                               "--format", "{{.Repository}}:{{.Tag}}"], capture_output=True, text=True, timeout=30)
        tags = proc.stdout.splitlines()
        if tags:
            subprocess.run(["docker", "image", "rm", *tags], capture_output=True, text=True, timeout=60)


@pytest.mark.slow
@pytest.mark.parametrize("scenario", ["passing", "failing", "no_submit", "crash", "solve_timeout", "setup_timeout", "judge_timeout"])
def test_real_docker_trial_lifecycle(docker_case, scenario):
    case, root = docker_case
    value = "0" if scenario == "failing" else "42"
    function = f"def value():\n    return {value}\n"
    if scenario == "judge_timeout":
        function = "def value():\n    import time\n    time.sleep(30)\n    return 42\n"
    import shlex
    command = ("mkdir -p /app/src; printf 'partial work\\n' > /app/partial.txt; "
               f"printf %s {shlex.quote(function)} > /app/src/answer.py; printf 'solver output\\n'; ")
    if scenario == "solve_timeout":
        command += "sleep 30"
    elif scenario != "no_submit":
        command += "printf 'CODINGBENCH_SUBMIT\\n' > /logs/agent/submit"
    if scenario == "crash":
        command = f"( {command}; exit 7 ) 2>&1 | tee /logs/agent/agent.txt"
    spec = {"name": "offline-control", "command": command, "setup_script": "printf 'setup ready\\n'", "env_passthrough": []}
    if scenario == "setup_timeout":
        spec.update(setup_script="printf 'setup timeout output\\n'; sleep 30", setup_timeout_sec=0.25)
    spec_path = root / f"{scenario}.json"
    atomic_json(spec_path, spec)
    out = root / f"run-{scenario}"
    result = run_trial(case, agent_spec_path=spec_path, model="offline/no-model", out_dir=out,
                       cache_root=root / "cache", limits=Limits(1 if scenario == "solve_timeout" else 10,
                                                               2 if scenario == "judge_timeout" else 20, 0))
    saved = json.loads((out / "trial.json").read_text())
    assert saved["finished_at"]
    assert saved["artifact_errors"] == []
    if scenario in {"passing", "failing", "crash"}:
        assert result.evaluated, result.to_dict()
        assert result.reward == (0 if scenario == "failing" else 1)
        assert result.agent_exit_code == (7 if scenario == "crash" else 0)
        assert result.terminal_status == ("error" if scenario == "crash" else "completed")
    elif scenario in {"no_submit", "solve_timeout"}:
        assert result.pipeline_status == "not_submitted", result.to_dict()
        assert result.judge_exit_code is None
        assert result.terminal_status == ("timeout" if scenario == "solve_timeout" else "error")
        assert list((out / "workspace").rglob("partial.txt")), "partial work must survive teardown"
    elif scenario == "setup_timeout":
        assert result.failed_phase == "setup", result.to_dict()
        assert result.error == "agent setup timed out"
    else:
        assert result.failed_phase == "judge", result.to_dict()
        assert "timed out" in result.judge_error
        assert (out / "judge_result.json").is_file()


@pytest.mark.slow
def test_real_cache_follows_changed_contract_and_cli_request(docker_case, monkeypatch):
    from cbrun import images
    case, root = docker_case
    original = images.ensure_agent_image(case.name, case_dir=case, cache_root=root / "cache", backend="custom")
    contract = case / "public/Interface_Contract.md"
    contract.write_text(contract.read_text() + "\nNew public requirement for cache regression.\n")
    changed = images.ensure_agent_image(case.name, case_dir=case, cache_root=root / "cache", backend="custom")
    assert image_identity(changed.agent_image)["id"] != image_identity(original.agent_image)["id"]
    assert changed.tests_cache_dir != original.tests_cache_dir
    c = Container.start(changed.agent_image, network="none")
    try:
        assert "New public requirement" in c.exec("cat /environment/Interface_Contract.md").tail
    finally:
        c.remove()
    # Changing a requested installer must not silently reuse the old image.
    # Deliberately fail the new installer instead of downloading any CLI.
    monkeypatch.setattr(images, "_cli_install_snippet", lambda *a, **k: "echo requested-new-cli; exit 19")
    with pytest.raises(RuntimeError, match="docker build"):
        images.ensure_agent_image(case.name, case_dir=case, cache_root=root / "cache", backend="custom")


def test_credentials_are_forwarded_without_entering_docker_arguments(monkeypatch):
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout='ok', stderr='')
    monkeypatch.setattr(subprocess, 'run', run)
    Container('fixture').exec('true', env={'OPENAI_API_KEY': 'dummy-secret-for-test'})
    argv, kwargs = calls[0]
    assert 'dummy-secret-for-test' not in ' '.join(argv)
    assert kwargs['env']['OPENAI_API_KEY'] == 'dummy-secret-for-test'


def test_preflight_failure_sets_batch_failure_and_saves_trial(tmp_path):
    case = make_case(tmp_path / 'cases')
    contract = case / 'public/Interface_Contract.md'
    contract.write_text(contract.read_text() + '\nforbidden_upstream\n')
    out = tmp_path / 'output'
    assert main(['--all', '--cases-root', str(case.parent), '--model', 'offline/no-model', '--out', str(out)]) == 1
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['complete']
    assert summary['aggregate']['not_evaluated'] == 1
    result = json.loads((out / case.name / 'codex/trial.json').read_text())
    assert result['failed_phase'] == 'preflight'
    assert result['agent_exit_code'] is None
    assert result['finished_at']


def test_score_zero_does_not_make_a_batch_fail(tmp_path, monkeypatch):
    import cbrun.cli as cli
    from cbrun.results import TrialResult
    case = make_case(tmp_path / 'cases')
    monkeypatch.setattr(cli, 'run_trial', lambda *a, **k: TrialResult(case.name, 'codex', 'm', 0.0,
        'completed', pipeline_status='evaluated', phase='complete'))
    out = tmp_path / 'output'
    assert main(['--all', '--cases-root', str(case.parent), '--model', 'offline/no-model', '--out', str(out)]) == 0
    summary = json.loads((out / 'summary.json').read_text())
    assert summary['aggregate']['evaluated'] == 1
    assert summary['aggregate']['passed'] == 0


def test_resource_archives_cannot_escape_the_model_directory(tmp_path):
    import importlib.util
    import zipfile
    path = BENCHMARK / 'cases/case010/source/env/fetch_resources.py'
    spec = importlib.util.spec_from_file_location('resource_installer_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    archive = tmp_path / 'unsafe.zip'
    with zipfile.ZipFile(archive, 'w') as output:
        output.writestr('../outside', 'forbidden')
    with pytest.raises(ValueError, match='unsafe archive'):
        module.extract(archive, tmp_path / 'models', 100)
    assert not (tmp_path / 'outside').exists()


def test_image_preflight_forwards_declared_gpus(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from cbrun import cli, images, preflight, run_case
    case = make_case(tmp_path / 'cases')
    path = case / 'source/manifest.json'
    data = json.loads(path.read_text())
    data['runner']['docker_gpus'] = 'all'
    atomic_json(path, data)
    calls = []
    class Fake:
        def remove(self): pass
    def start(image, **kwargs):
        calls.append(kwargs)
        return Fake()
    monkeypatch.setattr(Container, 'start', start)
    monkeypatch.setattr(images, 'ensure_agent_image', lambda *a, **k: SimpleNamespace(agent_image='fixture'))
    monkeypatch.setattr(cli, 'image_identity', lambda *a: {'id': 'fixture'})
    monkeypatch.setattr(preflight, 'check_container', lambda *a, **k: {})
    monkeypatch.setattr(run_case, '_probe_cli_version', lambda *a: 'fixture-cli')
    assert main(['--all', '--cases-root', str(case.parent), '--preflight', '--check-images', '--out', str(tmp_path/'out')]) == 0
    assert len(calls) == 2
    assert all(call['gpus'] == 'all' for call in calls)


def test_non_pytest_case_does_not_require_pytest(tmp_path):
    from cbrun.preflight import check_container
    from cbrun.docker_env import ExecResult
    case = make_case(tmp_path)
    path = case / 'milestones/final/test_manifest.json'
    manifest = json.loads(path.read_text())
    manifest['test_command'] = 'node --test'
    atomic_json(path, manifest)
    source = case / 'source/manifest.json'
    data = json.loads(source.read_text())
    data['runner']['environment_checks'] = []
    atomic_json(source, data)
    commands = []
    class Fake:
        def exec(self, command, **kwargs):
            commands.append(command)
            return ExecResult(exit_code=0)
    check_container(Fake(), case, phase='judge')
    assert all('import pytest' not in command for command in commands)


@pytest.mark.slow
def test_custom_cli_can_be_installed_before_version_probe(docker_case):
    case, root = docker_case
    spec = root / 'custom-install.json'
    command = "mkdir -p /app/src; printf 'def value():\\n    return 42\\n' > /app/src/answer.py; printf 'CODINGBENCH_SUBMIT\\n' > /logs/agent/submit"
    atomic_json(spec, {'name': 'codex', 'command': command, 'env_passthrough': [],
        'install_script': "printf '#!/bin/sh\\nprintf custom-cli-version\\n' > /usr/local/bin/codex; chmod +x /usr/local/bin/codex"})
    result = run_trial(case, agent_spec_path=spec, model='offline/no-model', out_dir=root/'custom-install-run',
                       cache_root=root/'cache', limits=Limits(10,20,0))
    assert result.evaluated, result.to_dict()
    assert result.cli_version == 'custom-cli-version'
