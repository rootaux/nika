import logging
import os
import tempfile

from config_provider import ConfigProvider
from utils.common import execute_command


class OpenGrepRunner:

    def run(self, repo_path: str, rules_path: str, baseline_commit: str | None = None):
        config = ConfigProvider.get_config()
        opengrep_path = (config.tools.get("opengrep") or {}).get("path")
        if not opengrep_path:
            raise RuntimeError("config.tools.opengrep.path is not set")
        tf = tempfile.NamedTemporaryFile(delete=False)
        output_file = tf.name
        tf.close()
        temp_index_path = None

        try:
            cmd = [
                opengrep_path,
                "--config",
                rules_path,
                repo_path,
                "--json",
                f"--json-output={output_file}",
            ]

            if baseline_commit:
                logging.info(
                    "Running OpenGrep with baseline commit: %s", baseline_commit
                )
                cmd.extend(["--baseline-commit", baseline_commit])

            result = execute_command(cmd, shell=False, cwd=repo_path)
            if result.ok:
                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    with open(output_file, "r", encoding="utf-8") as handle:
                        return handle.read()
                return result.stdout or '{"results": []}'

            raise RuntimeError(
                f"OpenGrep check failed: {result.stderr or result.stdout} for rules at {rules_path}"
            )
        except Exception as exc:
            logging.error("OpenGrep execution failed: %s", exc)
            raise
        finally:
            if os.path.exists(output_file):
                os.remove(output_file)
            if temp_index_path:
                for candidate in [temp_index_path, f"{temp_index_path}.lock"]:
                    if os.path.exists(candidate):
                        os.remove(candidate)
