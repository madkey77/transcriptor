from typer.testing import CliRunner
from src.cli.app import app

runner = CliRunner()


def test_version_flag_prints_version_and_exits_zero():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.stdout


def test_help_lists_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("transcribe", "submit", "jobs"):
        assert cmd in result.stdout


def test_quiet_flag_suppresses_human_messages(tmp_path):
    # Arquivo inexistente gera erro humano em stderr; com --quiet só JSON em stdout
    result = runner.invoke(
        app,
        ["--quiet", "submit", str(tmp_path / "ghost.mp3"), "--server", "http://srv"],
    )
    assert result.exit_code == 2
    # stderr ainda pode ter mensagem; stdout deve estar vazio para um erro de usage
    # (não deve conter JSON de resposta)
    assert "transcription_id" not in result.stdout
