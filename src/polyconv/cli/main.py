"""The command line interface for polyconv. The command is `polyconv`."""

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from polyconv.test_data import DEFAULT_OUT_DIR, generate_cms_tests


def make_parser() -> ArgumentParser:
    """Create the command line parser for the polyconv CLI."""
    parser = ArgumentParser()
    parser.add_argument("polygon_path", help="Path to the Polygon package folder.")
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force overwrite existing tests."
    )
    parser.add_argument(
        "--out",
        "-o",
        type=Path,
        default=None,
        help="Path to the output folder. Defaults to "
        f"<polygon_path>/{DEFAULT_OUT_DIR}.",
    )
    parser.add_argument(
        "--output-only",
        metavar="SUBSTRING",
        help="Also extract tests whose group contains SUBSTRING into CMS OutputOnly "
        "dataset and attachment archives.",
    )
    parser.add_argument(
        "--samples",
        metavar="GROUP",
        help="Also extract tests whose group exactly matches GROUP into samples.zip.",
    )
    return parser


def generate_test_data(args: Namespace) -> None:
    """Generate test data and score parameters for CMS from Polygon tests."""
    polygon_path = Path(args.polygon_path).resolve()
    score_params, output_only_score_params = generate_cms_tests(
        polygon_path,
        output_path=args.out,
        overwrite=args.force,
        output_only=args.output_only,
        samples=args.samples,
    )
    print(f"CMS Batch Score Parameters:\n{score_params}")
    if output_only_score_params is not None:
        print(f"CMS OutputOnly Score Parameters:\n{output_only_score_params}")


def main() -> None:
    """Run the polyconv CLI."""
    try:
        parser = make_parser()
        args = parser.parse_args()
        generate_test_data(args)
    except (FileExistsError, ValueError) as e:
        print(f"Error: {e}")
        sys.exit(1)
