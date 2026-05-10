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


from src.cli.commands import submit as _submit_module

app.command(name="submit", help="Envia arquivos pro backend HTTP e (opcional) baixa resultado.")(_submit_module.run)


from src.cli.commands import jobs as _jobs_module

app.add_typer(_jobs_module.app, name="jobs")
