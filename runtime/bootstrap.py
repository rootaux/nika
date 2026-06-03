import logging
import sys
import traceback

from config_provider import ConfigProvider
from runtime.arg_parser import parse_and_validate_arguments
from runtime.cli import build_scan_context
from runtime.runtime import NikaApplicationRuntime
from runtime.version import APP_VERSION
from utils.common import execute_command


def get_banner() -> str:
    return f"""
  _   _ _ _
 | \\ | (_) | ____ _
 |  \\| | | |/ / _` |
 | |\\  | |   < (_| |
 |_| \\_|_|_|\\_\\__,_|

 Static Code Review Analysis Tool

 Version: {APP_VERSION}
"""


def setup_logging():
    print(get_banner())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def compute_baseline_commit(args):
    source_branch = getattr(args, "source_branch", None)
    target_branch = getattr(args, "target_branch", None)
    code_path = getattr(args, "path", None)

    if not source_branch or not target_branch:
        return None

    result = execute_command(
        [
            "git",
            "merge-base",
            f"origin/{source_branch}",
            f"origin/{target_branch}",
        ],
        cwd=code_path,
    )
    if result.returncode == 0:
        return result.stdout.strip()

    fallback = execute_command(
        ["git", "merge-base", source_branch, target_branch],
        cwd=code_path,
    )
    if fallback.returncode == 0:
        return fallback.stdout.strip()

    logging.info("Error determining baseline commit: %s", fallback.stderr)
    return None


def build_request(args):
    args.baseline_commit = compute_baseline_commit(args)
    return build_scan_context(args, [], {}, False)


def run_cli():
    setup_logging()
    try:
        args = parse_and_validate_arguments()
        if getattr(args, "config", None):
            ConfigProvider.configure(args.config)
        request = build_request(args)
        NikaApplicationRuntime().run(request)
    except KeyboardInterrupt:
        logging.info("Shutdown requested by user. Exiting gracefully.")
        sys.exit(130)
    except Exception as exc:
        logging.info("Fatal error: %s", exc)
        traceback.print_exc()
        sys.exit(1)
