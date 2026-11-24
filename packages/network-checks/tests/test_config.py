"""Profile selection. Switching product is a config change, not a new suite."""

from pathlib import Path

import pytest

from network_checks.load_config import ConfigError, load_profile, load_runner_env, project_root

PROFILES = ("ecommerce", "erp", "cms", "fintech")


@pytest.mark.parametrize("name", PROFILES)
def test_profile_switch(name: str, case) -> None:
    profile = load_profile(name)
    case.actual = (
        f"name={profile['name']}; hosts={len(profile['hosts'])}; "
        f"criticalPort={profile['criticalPort']}; readOnly={profile['readOnly']}"
    )
    assert profile["name"] == name
    assert profile["hosts"]
    assert profile["http"]["baseUrl"].startswith("https://")
    assert profile["criticalPort"] == 443
    assert profile["readOnly"] is True


def test_each_profile_keeps_its_overlay(monkeypatch: pytest.MonkeyPatch, case) -> None:
    """Assert against the committed example so a local product YAML can rename overlays."""
    example = project_root() / "config" / "targets.example.yaml"
    monkeypatch.setenv("TARGETS_FILE", str(example))
    overlays = {
        "ecommerce": ["checkout-api"],
        "erp": ["erp-api"],
        "cms": ["graphql-origin"],
        "fintech": ["payment-gateway", "webhook-receiver"],
    }
    found_map = {}
    for name, required in overlays.items():
        found = [item["name"] for item in load_profile(name)["overlays"]]
        found_map[name] = found
        for overlay in required:
            assert overlay in found
    case.actual = str(found_map)


def test_unknown_profile_rejected(case) -> None:
    with pytest.raises(ConfigError, match="cms") as caught:
        load_profile("does-not-exist")
    case.actual = f"raised={type(caught.value).__name__}: {caught.value}"


def test_missing_local_file_uses_the_example(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    example = (project_root() / "config" / "targets.example.yaml").read_text(encoding="utf-8")
    (config_dir / "targets.example.yaml").write_text(example, encoding="utf-8")
    monkeypatch.setattr("network_checks.load_config.project_root", lambda: tmp_path)
    monkeypatch.delenv("TARGETS_FILE", raising=False)
    profile = load_profile("cms")
    case.actual = (
        f"usingExampleTargets={profile['usingExampleTargets']}; "
        f"targetsFile={profile['targetsFile']}"
    )
    assert profile["usingExampleTargets"] is True
    assert profile["targetsFile"].endswith("targets.example.yaml")


def test_targets_file_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case) -> None:
    source = project_root() / "config" / "targets.example.yaml"
    target = tmp_path / "targets.yaml"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("TARGETS_FILE", str(target))
    profile = load_profile("erp")
    case.actual = (
        f"name={profile['name']}; targetsFile={profile['targetsFile']}; "
        f"usingExampleTargets={profile['usingExampleTargets']}"
    )
    assert profile["name"] == "erp"
    assert profile["targetsFile"] == str(target.resolve())
    assert profile["usingExampleTargets"] is False


def test_minimal_profile_does_not_invent_a_public_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case
) -> None:
    target = tmp_path / "targets.yaml"
    target.write_text(
        """
cms:
  hosts: [api.cms.staging.example.com]
  ports: [443]
  http:
    baseUrl: https://api.cms.staging.example.com
    healthPath: /health
    expectedStatus: [200]
  latencyMs: 800
  timeoutSec: 5
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("TARGETS_FILE", str(target))
    profile = load_profile("cms")
    case.actual = (
        f"redirectUrl={profile['http'].get('redirectUrl', '-')}; "
        f"multiAHost={profile['dns']['multiAHost']}; "
        f"unreachableHost={profile['unreachableHost']}"
    )
    assert profile["http"]["baseUrl"] == "https://api.cms.staging.example.com"
    assert profile["http"]["healthPath"] == "/health"
    assert profile["latencyMs"] == 800
    assert profile["criticalPort"] == 443
    assert "redirectUrl" not in profile["http"]
    assert profile["dns"]["multiAHost"] == "api.cms.staging.example.com"
    assert profile["unreachableHost"] == "192.0.2.1"


def test_dotenv_sets_profile_when_shell_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case
) -> None:
    source = project_root() / "config" / "targets.example.yaml"
    target = tmp_path / "targets.yaml"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"NETWORK_PROFILE=fintech\nTARGETS_FILE={target}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("NETWORK_PROFILE", raising=False)
    monkeypatch.delenv("TARGETS_FILE", raising=False)
    load_runner_env(env_file, force=True)
    profile = load_profile()
    case.actual = f"name={profile['name']}; targetsFile={profile['targetsFile']}"
    assert profile["name"] == "fintech"
    assert profile["targetsFile"] == str(target.resolve())


def test_shell_env_wins_over_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case) -> None:
    source = project_root() / "config" / "targets.example.yaml"
    target = tmp_path / "targets.yaml"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"NETWORK_PROFILE=fintech\nTARGETS_FILE={target}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NETWORK_PROFILE", "erp")
    monkeypatch.setenv("TARGETS_FILE", str(target))
    load_runner_env(env_file, force=True)
    profile = load_profile()
    case.actual = f"name={profile['name']}"
    assert profile["name"] == "erp"
