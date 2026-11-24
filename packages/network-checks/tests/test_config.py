"""Dynamic site profile from TARGET_URL; YAML is only a fallback."""

from pathlib import Path

import pytest

from network_checks.load_config import ConfigError, load_profile, project_root


def test_target_url_builds_one_site_profile(
    monkeypatch: pytest.MonkeyPatch, case
) -> None:
    monkeypatch.setenv("TARGET_URL", "https://example.com/")
    monkeypatch.delenv("NETWORK_PROFILE", raising=False)
    monkeypatch.delenv("TARGETS_FILE", raising=False)
    profile = load_profile()
    case.actual = (
        f"name={profile['name']}; host={profile['hosts'][0]}; "
        f"baseUrl={profile['http']['baseUrl']}; targetsFile={profile['targetsFile']}"
    )
    assert profile["name"] == "site"
    assert profile["hosts"] == ["example.com"]
    assert profile["http"]["baseUrl"] == "https://example.com"
    assert profile["http"]["healthPath"] == "/"
    assert profile["http"]["redirectUrl"] == "http://example.com/"
    assert profile["criticalPort"] == 443
    assert profile["readOnly"] is True
    assert profile["targetsFile"] == "(dynamic from TARGET_URL)"
    assert profile["usingExampleTargets"] is False


def test_target_url_wins_over_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case
) -> None:
    target = tmp_path / "targets.yaml"
    target.write_text(
        """
site:
  hosts: [yaml.example.com]
  ports: [443]
  http:
    baseUrl: https://yaml.example.com
    healthPath: /health
    expectedStatus: [200]
  latencyMs: 800
  timeoutSec: 5
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("TARGETS_FILE", str(target))
    monkeypatch.setenv("TARGET_URL", "https://from-url.example/")
    profile = load_profile()
    case.actual = f"host={profile['hosts'][0]}; baseUrl={profile['http']['baseUrl']}"
    assert profile["hosts"] == ["from-url.example"]
    assert profile["http"]["baseUrl"] == "https://from-url.example"


def test_yaml_site_fallback_without_target_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case
) -> None:
    target = tmp_path / "targets.yaml"
    target.write_text(
        """
site:
  hosts: [api.staging.example.com]
  ports: [443]
  http:
    baseUrl: https://api.staging.example.com
    healthPath: /health
    expectedStatus: [200]
  latencyMs: 800
  timeoutSec: 5
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("TARGET_URL", raising=False)
    monkeypatch.setenv("TARGETS_FILE", str(target))
    profile = load_profile()
    case.actual = (
        f"name={profile['name']}; host={profile['hosts'][0]}; "
        f"redirectUrl={profile['http'].get('redirectUrl', '-')}"
    )
    assert profile["name"] == "site"
    assert profile["hosts"] == ["api.staging.example.com"]
    assert profile["criticalPort"] == 443
    assert "redirectUrl" not in profile["http"]
    assert profile["dns"]["multiAHost"] == "api.staging.example.com"
    assert profile["unreachableHost"] == "192.0.2.1"


def test_unknown_profile_rejected(monkeypatch: pytest.MonkeyPatch, case) -> None:
    monkeypatch.delenv("TARGET_URL", raising=False)
    with pytest.raises(ConfigError, match="site") as caught:
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
    monkeypatch.delenv("TARGET_URL", raising=False)
    monkeypatch.delenv("TARGETS_FILE", raising=False)
    profile = load_profile("site")
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
    monkeypatch.delenv("TARGET_URL", raising=False)
    monkeypatch.setenv("TARGETS_FILE", str(target))
    profile = load_profile("site")
    case.actual = (
        f"name={profile['name']}; targetsFile={profile['targetsFile']}; "
        f"usingExampleTargets={profile['usingExampleTargets']}"
    )
    assert profile["name"] == "site"
    assert profile["targetsFile"] == str(target.resolve())
    assert profile["usingExampleTargets"] is False


def test_bad_target_url_rejected(monkeypatch: pytest.MonkeyPatch, case) -> None:
    monkeypatch.setenv("TARGET_URL", "ftp://example.com/")
    with pytest.raises(ConfigError, match="http:// or https://") as caught:
        load_profile()
    case.actual = f"raised={type(caught.value).__name__}: {caught.value}"
