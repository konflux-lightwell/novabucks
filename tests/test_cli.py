import pytest

from novabucks.cli import main


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_no_subcommand_exits_with_code_2(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code == 2


def test_sign_not_implemented(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["sign"])
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "not yet implemented" in captured.err
