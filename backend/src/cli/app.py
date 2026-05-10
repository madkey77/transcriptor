from importlib.metadata import PackageNotFoundError, version
from typing import Optional

import typer

app = typer.Typer(
    name="transcriptor",
    help="Transcriptor CLI — modo standalone (WhisperX local) e cliente HTTP do backend.",
    no_args_is_help=True,
    add_completion=False,
)


def _resolve_version() -> str:
    try:
        return version("transcriptor")
    except PackageNotFoundError:
        return "0.1.0"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(_resolve_version())
        raise typer.Exit(code=0)


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Imprime a versão e sai.",
    ),
) -> None:
    """Root callback — registra opções globais."""
    return None


# Subcomandos serão registrados em tasks seguintes:
#   from src.cli.commands import transcribe, submit, jobs
#   app.command()(transcribe.run)
#   app.command()(submit.run)
#   app.add_typer(jobs.app, name="jobs")


@app.command(name="transcribe", help="Transcreve arquivos localmente (precisa de [full]).")
def _transcribe_placeholder() -> None:
    typer.secho("Comando 'transcribe' ainda não implementado.", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)


@app.command(name="submit", help="Envia arquivos para o backend HTTP.")
def _submit_placeholder() -> None:
    typer.secho("Comando 'submit' ainda não implementado.", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)


jobs_app = typer.Typer(help="Lista, consulta e remove transcrições no servidor.")
app.add_typer(jobs_app, name="jobs")


@jobs_app.command(name="list")
def _jobs_list_placeholder() -> None:
    typer.secho("Comando 'jobs list' ainda não implementado.", err=True, fg=typer.colors.RED)
    raise typer.Exit(code=1)
