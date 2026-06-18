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


def test_sign_not_implemented():
    runner = CliRunner()
    result = runner.invoke(main, ["sign"])
    assert result.exit_code == 1
    assert "not yet implemented" in result.output
