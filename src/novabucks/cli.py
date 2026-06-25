"""
Copyright (C) 2022 Red Hat, Inc. (https://github.com/Commonjava/charon)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

         http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import logging
import os
import sys
import traceback
from typing import List

import click

from novabucks import __version__
from novabucks.utils.logs import set_logging
from novabucks.utils.storage import safe_delete
from novabucks.workflows import sign_in_radas_workflow, sign_individual_artifacts_workflow

logger = logging.getLogger(__name__)


def _log_mode(action_name, is_quiet, is_debug, use_log_file=True):
    if is_quiet:
        logger.info("Quiet mode enabled, will only give warning and error logs.")
        set_logging(action_name, level=logging.WARNING, use_log_file=use_log_file)
    elif is_debug:
        logger.info("Debug mode enabled, will give all debug logs for tracing.")
        set_logging(action_name, level=logging.DEBUG, use_log_file=use_log_file)
    else:
        set_logging(action_name, level=logging.INFO, use_log_file=use_log_file)


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="novabucks")
@click.pass_context
def main(ctx):
    """CLI tool for signing Maven artifacts."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit(2)


_RADAS_ENV_VARS = {
    "RADAS_UMB_HOST": "umb_host",
    "RADAS_UMB_HOST_PORT": "umb_host_port",
    "RADAS_RESULT_QUEUE": "result_queue",
    "RADAS_REQUEST_CHANNEL": "request_channel",
    "RADAS_CLIENT_CA": "client_ca",
    "RADAS_CLIENT_KEY": "client_key",
    "RADAS_CLIENT_KEY_PASS_FILE": "client_key_pass_file",
    "RADAS_ROOT_CA": "root_ca",
    "RADAS_QUAY_REGISTRY_CONFIG": "quay_radas_registry_config",
    "RADAS_SIGN_TIMEOUT_RETRY_COUNT": "radas_sign_timeout_retry_count",
    "RADAS_SIGN_TIMEOUT_RETRY_INTERVAL": "radas_sign_timeout_retry_interval",
    "RADAS_RECEIVER_TIMEOUT": "radas_receiver_timeout",
}

_RADAS_INT_FIELDS = {"radas_sign_timeout_retry_count", "radas_sign_timeout_retry_interval", "radas_receiver_timeout"}


def _build_radas_config_from_env():
    config = {}
    for env_var, config_key in _RADAS_ENV_VARS.items():
        value = os.environ.get(env_var)
        if value is not None:
            if config_key in _RADAS_INT_FIELDS:
                value = int(value)
            config[config_key] = value
    return config


@main.command()
@click.argument("repo_url")
@click.option("--requester", "-r", required=True, help="The requester who sends the signing request.")
@click.option("--result-path", "-p", required=True, help="The path which will save the sign result file.")
@click.option("--ignore-patterns", "-i", multiple=True, help="Regex patterns to filter out files from signing.")
@click.option("--config", "-c", type=click.File("r"), help="The radas configuration file path in JSON format.")
@click.option(
    "--config-from-env",
    "-e",
    is_flag=True,
    default=False,
    help="Read radas configuration from RADAS_* environment variables instead of a config file.",
)
@click.option("--sign-key", "-k", required=True, help="rpm-sign key to be used.")
@click.option("--debug", "-D", is_flag=True, default=False, help="Debug mode.")
@click.option("--quiet", "-q", is_flag=True, default=False, help="Quiet mode.")
def sign_repo_url(repo_url, requester, result_path, ignore_patterns, config, config_from_env, sign_key, debug, quiet):
    """Sign Maven artifacts in the given repo URL through radas service.

    This command will generate a single sign result json file with all the signed artifacts.
    """
    if config and config_from_env:
        raise click.UsageError("--config and --config-from-env are mutually exclusive.")
    if not config and not config_from_env:
        raise click.UsageError("Either --config or --config-from-env must be provided.")

    _log_mode("repo_signing", is_quiet=quiet, is_debug=debug)
    logger.debug("%s", ignore_patterns)
    try:
        if config_from_env:
            radas_config = _build_radas_config_from_env()
        else:
            radas_config = json.load(config)
        sign_in_radas_workflow(repo_url, requester, sign_key, result_path, ignore_patterns, radas_config)
    except SystemExit:
        raise
    except Exception:
        print(traceback.format_exc())
        sys.exit(2)


@main.command()
@click.argument("repos", type=str, nargs=-1)  # This allows multiple arguments for zip urls
@click.option(
    "--product",
    "-p",
    help="""
    The product key, will combine with version to decide
    the metadata of the files in tarball.
    """,
    nargs=1,
    required=True,
    multiple=False,
)
@click.option(
    "--version",
    "-v",
    help="""
    The product version, will combine with key to decide
    the metadata of the files in tarball.
    """,
    required=True,
    multiple=False,
)
@click.option(
    "--root_path",
    "-r",
    default="maven-repository",
    help="""
    The root path in the tarball before the real maven paths,
    will be trailing off before copying to the destination directory.
    """,
)
@click.option(
    "--ignore_patterns",
    "-i",
    multiple=True,
    help="""
    The regex patterns list to filter out the files which should
    not be allowed to upload to S3. Can accept more than one pattern.
    """,
)
@click.option(
    "--work_dir",
    "-w",
    help="""
    The temporary working directory into which archives should
    be extracted, when needed.
    """,
)
@click.option(
    '--destination_dir',
    '-o',
    help="""
    The destination directory to all the files and alongisde the .asc files to be copied.
    """,
    default="signed-artifacts",
)
@click.option(
    "--debug", "-D", help="Debug mode, will print all debug logs for problem tracking.", is_flag=True, default=False
)
@click.option(
    "--quiet",
    "-q",
    help="Quiet mode, will shrink most of the logs except warning and errors.",
    is_flag=True,
    default=False,
)
@click.option(
    "--sign_result_file",
    "-l",
    help="""
    The path of the file which contains radas signature result.
    It will use the file to generate the corresponding .asc files which will be
    copied to the destination directory.
    """,
)
def generate_sign_files(
    repos: List[str],
    product: str,
    version: str,
    root_path="maven-repository",
    ignore_patterns: List[str] = None,
    work_dir: str = None,
    destination_dir: str = None,
    debug=False,
    quiet=False,
    sign_result_file=None,
):
    """Generate .asc files based on the sign result json file."""
    tmp_dir = work_dir
    _log_mode("artifacts_signing", is_quiet=quiet, is_debug=debug)
    logger.debug("%s", ignore_patterns)
    try:
        product_key = f"{product}-{version}"
        sign_individual_artifacts_workflow(
            repos,
            product_key,
            root_path,
            ignore_patterns,
            work_dir,
            destination_dir,
            sign_result_file,
        )
    except Exception:
        print(traceback.format_exc())
        sys.exit(2)  # distinguish between exception and bad config or bad state
    finally:
        if not debug and tmp_dir:
            safe_delete(tmp_dir)
