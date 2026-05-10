import logging
import sys
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


def _configure_logging(quiet: bool, verbose: bool) -> None:
    if quiet and verbose:
        raise typer.BadParameter("--quiet and --verbose are mutually exclusive")
    if verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    elif quiet:
        logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Imprime a versão e sai.",
    ),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suprime mensagens humanas."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Logs detalhados em stderr."),
) -> None:
    """Root callback — registra opções globais."""
    _configure_logging(quiet, verbose)


# Subcomandos serão registrados em tasks seguintes:
#   from src.cli.commands import transcribe, submit, jobs
#   app.command()(transcribe.run)
#   app.command()(submit.run)
#   app.add_typer(jobs.app, name="jobs")


from src.cli.commands import transcribe as _transcribe_module

app.command(name="transcribe", help="Transcreve arquivos localmente (precisa de [full]).")(_transcribe_module.run)


from src.cli.commands import submit as _submit_module

app.command(name="submit", help="Envia arquivos pro backend HTTP e (opcional) baixa resultado.")(_submit_module.run)


from src.cli.commands import jobs as _jobs_module

app.add_typer(_jobs_module.app, name="jobs")
