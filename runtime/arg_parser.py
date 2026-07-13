import argparse
import logging
import sys


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Code Review Tool - Static Code Review Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --path /path/to/source --lang java --output report.html
        """,
    )

    parser.add_argument(
        "--path",
        required=True,
        help="Path to source directory/git repository to analyze",
    )

    parser.add_argument(
        "--source_branch",
        default=None,
        help="Branch to analyze in git repository (default: main)",
    )

    parser.add_argument(
        "--target_branch",
        default=None,
        help="Branch to compare against in git repository (default: None)",
    )

    parser.add_argument(
        "--lang",
        default="java",
        choices=["java"],
        help="Programming language of the codebase (default: java)",
    )

    parser.add_argument(
        "--output",
        default="report.html",
        help="Path to save the HTML report (default: report.html)",
    )

    parser.add_argument(
        "--config",
        default=None,
        help="Path to the YAML config file (default: config/crtConfig.yml)",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Include extra diagnostic metadata (lines of code, call node counts, etc.) in the JSON report",
    )

    parser.add_argument(
        "--inference-jar-paths",
        nargs="+",
        default=None,
        metavar="PATH",
        help=(
            "Directories of (or individual) dependency jars used for type resolution"
        ),
    )

    return parser.parse_args()


def validate_arguments(args):
    """Validate parsed arguments."""
    if args.lang != "java":
        logging.info("Error: Language '%s' is not supported yet.", args.lang)
        logging.info("Currently supported languages: java")
        sys.exit(1)

    if not args.path:
        logging.info("Error: --path argument is required")
        sys.exit(1)


def parse_and_validate_arguments():
    if len(sys.argv) == 1:
        sys.argv.append("--help")

    args = parse_arguments()
    validate_arguments(args)
    return args
