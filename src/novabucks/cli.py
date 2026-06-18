import datetime
import json
import logging
import sys
import traceback

import click

from novabucks import __version__
from novabucks.constants import DEFAULT_RADAS_SIGN_IGNORES
from novabucks.radas_sign import RadasConfig, sign_in_radas
from novabucks.utils.logs import set_logging

logger = logging.getLogger(__name__)


def _decide_mode(product, version, is_quiet, is_debug, use_log_file=True):
    if is_quiet:
        logger.info("Quiet mode enabled, will only give warning and error logs.")
        set_logging(product, version, level=logging.WARNING, use_log_file=use_log_file)
    elif is_debug:
        logger.info("Debug mode enabled, will give all debug logs for tracing.")
        set_logging(product, version, level=logging.DEBUG, use_log_file=use_log_file)
    else:
        set_logging(product, version, level=logging.INFO, use_log_file=use_log_file)


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="novabucks")
@click.pass_context
def main(ctx):
    """CLI tool for signing Maven artifacts."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(2)


@main.command()
@click.argument("repo_url")
@click.option("--requester", "-r", required=True, help="The requester who sends the signing request.")
@click.option("--result-path", "-p", required=True, help="The path which will save the sign result file.")
@click.option("--ignore-patterns", "-i", multiple=True, help="Regex patterns to filter out files from signing.")
@click.option(
    "--config", "-c", type=click.File("r"), required=True, help="The radas configuration file path in JSON format."
)
@click.option("--sign-key", "-k", required=True, help="rpm-sign key to be used.")
@click.option("--debug", "-D", is_flag=True, default=False, help="Debug mode.")
@click.option("--quiet", "-q", is_flag=True, default=False, help="Quiet mode.")
def sign(repo_url, requester, result_path, ignore_patterns, config, sign_key, debug, quiet):
    """Sign Maven artifacts in the given repo URL through radas service."""
    logger.debug("%s", ignore_patterns)
    try:
        current = datetime.datetime.now().strftime("%Y%m%d%I%M")
        _decide_mode("radas_sign", current, is_quiet=quiet, is_debug=debug)
        conf = json.load(config)
        if not conf:
            logger.error("The novabucks configuration is not valid!")
            sys.exit(1)
        radas_data = conf.get("radas", {})
        radas_conf = RadasConfig(radas_data)
        if not radas_conf.validate():
            logger.error("The configuration for radas is not valid!")
            sys.exit(1)
        ig_patterns = list(conf.get("ignore_patterns", []))
        ig_patterns.extend(DEFAULT_RADAS_SIGN_IGNORES)
        if ignore_patterns:
            ig_patterns.extend(ignore_patterns)
        ig_patterns = list(set(ig_patterns))
        sign_in_radas(
            repo_url=repo_url,
            requester=requester,
            sign_key=sign_key,
            result_path=result_path,
            ignore_patterns=ig_patterns,
            radas_config=radas_conf,
        )
    except SystemExit:
        raise
    except Exception:
        print(traceback.format_exc())
        sys.exit(2)
