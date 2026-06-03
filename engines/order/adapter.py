from engines.order.scanner import OrderAnalyzer
from models.sink import Sink


class OrderSinkFinder:
    def find_sinks(self, context, rules_path: str):
        analyzer = OrderAnalyzer(rules_path=rules_path)
        raw_sinks = analyzer.analyze(path=context.path)

        sinks = []
        for item in raw_sinks:
            line_number = item.get("line_number")
            line_number_end = item.get("line_number_end")
            sinks.append(
                Sink(
                    file_path=item.get("file") or "",
                    line_number=int(line_number) if line_number else 0,
                    line_number_end=int(line_number_end) if line_number_end else 0,
                    code=item.get("code") or "",
                )
            )
        return sinks
