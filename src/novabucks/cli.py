import argparse
import sys

from novabucks import __version__


def _handle_sign(_args):
    print("sign: not yet implemented", file=sys.stderr)
    raise SystemExit(1)


def create_parser():
    parser = argparse.ArgumentParser(prog="novabucks", description="CLI tool for signing Maven artifacts")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("sign", help="Sign Maven artifacts")

    return parser


def main(argv=None):
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        raise SystemExit(2)

    handlers = {
        "sign": _handle_sign,
    }
    handlers[args.command](args)
