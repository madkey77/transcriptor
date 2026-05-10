from pathlib import Path

import pytest

from src.cli.config import CliSettings, load_settings


def test_defaults_when_nothing_set(tmp_path: Path):
    settings = load_settings(config_path=tmp_path / "absent.toml", profile=None)
    assert settings.server == "http://127.0.0.1:8000"
    assert settings.api_key is None
    assert settings.output_dir == Path("./output")
    assert settings.formats == ["srt", "txt", "json"]


def test_env_overrides_default(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("TRANSCRIPTOR_SERVER", "http://from-env:9000")
    monkeypatch.setenv("TRANSCRIPTOR_API_KEY", "envkey")
    monkeypatch.setenv("TRANSCRIPTOR_OUTPUT_DIR", str(tmp_path / "out"))

    settings = load_settings(config_path=tmp_path / "absent.toml", profile=None)

    assert settings.server == "http://from-env:9000"
    assert settings.api_key == "envkey"
    assert settings.output_dir == tmp_path / "out"


def test_toml_default_section_loaded(tmp_config_file: Path):
    tmp_config_file.write_text(
        '[default]\n'
        'server = "http://from-toml:8001"\n'
        'api_key = "tomlkey"\n'
        'formats = ["srt"]\n'
    )
    settings = load_settings(config_path=tmp_config_file, profile=None)
    assert settings.server == "http://from-toml:8001"
    assert settings.api_key == "tomlkey"
    assert settings.formats == ["srt"]


def test_profile_overrides_default_in_toml(tmp_config_file: Path):
    tmp_config_file.write_text(
        '[default]\n'
        'server = "http://default:8000"\n'
        'api_key = "defaultkey"\n'
        '\n'
        '[profiles.lan]\n'
        'server = "http://lan:8000"\n'
    )
    settings = load_settings(config_path=tmp_config_file, profile="lan")
    assert settings.server == "http://lan:8000"
    assert settings.api_key == "defaultkey"  # herdado do default


def test_env_overrides_toml(monkeypatch, tmp_config_file: Path):
    tmp_config_file.write_text('[default]\nserver = "http://toml:8000"\n')
    monkeypatch.setenv("TRANSCRIPTOR_SERVER", "http://env:9000")

    settings = load_settings(config_path=tmp_config_file, profile=None)
    assert settings.server == "http://env:9000"


def test_unknown_profile_raises(tmp_config_file: Path):
    tmp_config_file.write_text('[default]\nserver = "http://x"\n')
    with pytest.raises(ValueError, match="profile 'lan' not found"):
        load_settings(config_path=tmp_config_file, profile="lan")
