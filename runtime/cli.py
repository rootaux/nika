from models.scan_context import ScanContext
import os

def build_scan_context(
    args,
    enabled_vulnerabilities: list[str],
    engine_selection: dict[str, str],
    review_llm_enabled: bool,
) -> ScanContext:
    return ScanContext(
        path=os.path.abspath(args.path) if args.path else None,
        language=args.lang,
        output=args.output,
        source_branch=args.source_branch,
        target_branch=args.target_branch,
        baseline_commit=getattr(args, "baseline_commit", None),
        enabled_vulnerabilities=enabled_vulnerabilities,
        engine_selection=engine_selection,
        review_llm_enabled=review_llm_enabled,
        debug=getattr(args, "debug", False),
    )
