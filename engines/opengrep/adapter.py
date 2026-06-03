from engines.opengrep.runner import OpenGrepRunner
from engines.opengrep.translators import translate_opengrep_results


class OpenGrepSinkFinder:
    def __init__(self, runner=None):
        self.runner = runner or OpenGrepRunner()

    def find_sinks(self, context, rules_path: str):
        raw = self.runner.run(
            context.path,
            rules_path,
            getattr(context, "baseline_commit", None),
        )
        return translate_opengrep_results(raw, context.path)
