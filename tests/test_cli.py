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

from click.testing import CliRunner

from novabucks.cli import main


def test_version_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_no_subcommand_exits_with_code_2():
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 2


def test_sign_repo_url_missing_required_args():
    runner = CliRunner()
    result = runner.invoke(main, ["sign-repo-url"])
    assert result.exit_code != 0
    assert "Missing" in result.output or "Error" in result.output


def test_sign_repo_url_help():
    runner = CliRunner()
    result = runner.invoke(main, ["sign-repo-url", "--help"])
    assert result.exit_code == 0
    assert "--requester" in result.output
    assert "--result-path" in result.output
    assert "--config" in result.output
    assert "--sign-key" in result.output
    assert "REPO_URL" in result.output


def test_generate_sign_files_help():
    runner = CliRunner()
    result = runner.invoke(main, ["generate-sign-files", "--help"])
    assert result.exit_code == 0
    assert "--product" in result.output
    assert "--version" in result.output
    assert "REPOS" in result.output
