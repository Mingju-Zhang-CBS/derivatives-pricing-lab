import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='Numerical comparison and private EOD option diagnostics')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--benchmark', action='store_true')
    mode.add_argument('--quotes', type=Path)
    mode.add_argument('--fixture', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.benchmark:
        from .benchmark import run
        result = run(args.output)
    elif args.fixture:
        from .fixture import create_and_run
        result = create_and_run(args.output)
    else:
        from .quotes import run
        result = run(args.quotes, args.output)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
