import logging
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from threading import Lock

from engines.astrail.errors import AstrailEngineError
from models.degraded_finding import DegradedFinding


_ENGINE_RUN_LOCK = Lock()
_MAX_PARALLEL_WORKERS = 8


@dataclass(frozen=True)
class ScanRunStats:
    total_sources: int
    total_findings: int
    total_false_positives: int


class _SourceCacheEntry:
    def __init__(self):
        self.lock = Lock()
        self.ready = False
        self.value = ()


class ScanLifecycleHooks:
    def on_scan_start(self, request, vulnerabilities):
        return None

    def on_engine_prepare_start(self, role, engine_name):
        return None

    def on_engine_prepare_end(self, role, engine_name):
        return None

    def on_vulnerability_start(self, vulnerability_name):
        return None

    def on_vulnerability_end(self, vulnerability_name, finding_count):
        return None

    def on_scan_error(self, error):
        return None

    def on_cleanup_start(self):
        return None

    def on_cleanup_end(self, cleanup_error=None):
        return None

    def on_scan_end(self, total_findings):
        return None


def _safe_call_hook(hooks, name, *args):
    callback = getattr(hooks, name, None)
    if not callable(callback):
        return
    try:
        callback(*args)
    except Exception:
        return


class RuntimeExecutionContext:
    def __init__(self, request, language_pack, engines):
        self.path = request.path
        self.language = request.language
        self.output = request.output
        self.source_branch = request.source_branch
        self.target_branch = request.target_branch
        self.baseline_commit = request.baseline_commit
        self.review_llm_enabled = request.review_llm_enabled
        self.language_pack = language_pack
        self.engines = engines
        self._shared_sources = {}
        self._shared_sources_lock = Lock()

    def _source_cache_key(self, source_types):
        return tuple(sorted(set(source_types or [])))

    def get_or_discover_sources(self, source_types, discover_fn):
        key = self._source_cache_key(source_types)
        with self._shared_sources_lock:
            entry = self._shared_sources.get(key)
            if entry is None:
                entry = _SourceCacheEntry()
                self._shared_sources[key] = entry

        with entry.lock:
            if not entry.ready:
                discovered = discover_fn() or []
                entry.value = tuple(discovered)
                entry.ready = True
            return list(entry.value)

    def get_cached_sources(self, source_types):
        key = self._source_cache_key(source_types)
        with self._shared_sources_lock:
            entry = self._shared_sources.get(key)
        if entry is None:
            return None
        with entry.lock:
            if not entry.ready:
                return None
            return list(entry.value)

    def cache_sources(self, source_types, sources):
        self.get_or_discover_sources(source_types, lambda: sources)

    def total_discovered_sources(self) -> int:
        unique_sources = set()

        with self._shared_sources_lock:
            entries = list(self._shared_sources.values())

        for entry in entries:
            with entry.lock:
                if not entry.ready:
                    continue
                for source in entry.value:
                    unique_sources.add(
                        (
                            getattr(source, "file_path", None),
                            getattr(source, "line_number", None),
                            getattr(source, "symbol", None),
                            getattr(source, "source_type", None),
                        )
                    )

        return len(unique_sources)


class ScanRunner:
    def __init__(self, registry, lifecycle_hooks=None):
        self.registry = registry
        self.lifecycle_hooks = lifecycle_hooks or ScanLifecycleHooks()
        self.last_run_stats = None

    def _collect_run_stats(self, context, findings):
        total_false_positives = 0
        if getattr(context, "review_llm_enabled", False):
            total_false_positives = sum(
                1
                for finding in findings
                if getattr(finding, "status", "").strip().upper() == "NOT_VULNERABLE"
            )

        return ScanRunStats(
            total_sources=context.total_discovered_sources(),
            total_findings=len(findings),
            total_false_positives=total_false_positives,
        )

    def _request_uses_exclusive_engine(self, vulnerabilities, context):
        return any(
            self._vulnerability_uses_exclusive_engine(vulnerability, context)
            for vulnerability in vulnerabilities
        )

    def _engine_run_context(self, vulnerabilities, context):
        if self._request_uses_exclusive_engine(vulnerabilities, context):
            return _ENGINE_RUN_LOCK
        return nullcontext()

    def _requires_sequential_vulnerability_execution(self, vulnerabilities, context):
        return self._request_uses_exclusive_engine(vulnerabilities, context)

    def _vulnerability_uses_exclusive_engine(self, vulnerability, context):
        return any(
            getattr(context.engines.get(role), "requires_exclusive_run", False)
            for role in getattr(vulnerability, "required_engine_roles", [])
        )

    def _cleanup_engines(self, engines):
        cleanup_error = None
        cleaned_engines = set()
        for engine in engines.values():
            engine_id = id(engine)
            if engine_id in cleaned_engines:
                continue
            cleaned_engines.add(engine_id)
            cleanup = getattr(engine, "cleanup", None)
            if callable(cleanup):
                try:
                    cleanup()
                except Exception as exc:
                    if cleanup_error is None:
                        cleanup_error = exc
        if cleanup_error is not None:
            raise cleanup_error

    def _build_engines(self, request):
        engines = {}
        engine_cache = {}

        for role, name in request.engine_selection.items():
            entry = self.registry.engines[role][name]
            cache_key = (entry.factory, name, request.path)
            if cache_key not in engine_cache:
                engine_cache[cache_key] = self.registry.create_engine(role, name, request)
            engines[role] = engine_cache[cache_key]

        return engines

    def _prepare_engines(self, request, engines):
        prepared_engines = set()
        for role, engine_name in request.engine_selection.items():
            engine = engines[role]
            engine_id = id(engine)
            if engine_id in prepared_engines:
                continue
            prepared_engines.add(engine_id)

            _safe_call_hook(
                self.lifecycle_hooks,
                "on_engine_prepare_start",
                role,
                engine_name,
            )
            prepare = getattr(engine, "prepare", None)
            if callable(prepare):
                prepare()
            _safe_call_hook(
                self.lifecycle_hooks,
                "on_engine_prepare_end",
                role,
                engine_name,
            )

    def _run_vulnerability(self, vulnerability, context):
        vulnerability_name = getattr(
            vulnerability,
            "vulnerability_id",
            vulnerability.__class__.__name__,
        )
        _safe_call_hook(
            self.lifecycle_hooks,
            "on_vulnerability_start",
            vulnerability_name,
        )
        try:
            findings = vulnerability.run(context)
        except AstrailEngineError as exc:
            logging.warning(
                "Engine failure for %s: %s — marking as degraded",
                vulnerability_name,
                exc,
            )
            findings = [DegradedFinding(vulnerability_name, str(exc))]
        _safe_call_hook(
            self.lifecycle_hooks,
            "on_vulnerability_end",
            vulnerability_name,
            len(findings),
        )
        return findings

    def _run_vulnerabilities(self, vulnerabilities, context):
        if not vulnerabilities:
            return []

        def run_one(vulnerability):
            return self._run_vulnerability(vulnerability, context)

        if self._requires_sequential_vulnerability_execution(vulnerabilities, context):
            exclusive_vulnerabilities = []
            parallel_vulnerabilities = []
            for vulnerability in vulnerabilities:
                if self._vulnerability_uses_exclusive_engine(vulnerability, context):
                    exclusive_vulnerabilities.append(vulnerability)
                else:
                    parallel_vulnerabilities.append(vulnerability)

            results = [run_one(v) for v in exclusive_vulnerabilities]
            if parallel_vulnerabilities:
                workers = min(len(parallel_vulnerabilities), _MAX_PARALLEL_WORKERS)
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    results.extend(executor.map(run_one, parallel_vulnerabilities))
        else:
            workers = min(len(vulnerabilities), _MAX_PARALLEL_WORKERS)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                results = list(executor.map(run_one, vulnerabilities))

        findings = []
        for result in results:
            findings.extend(result)
        return findings

    def run(self, request):
        self.last_run_stats = None
        language_pack = self.registry.create_language(request.language)
        engines = self._build_engines(request)
        context = RuntimeExecutionContext(request, language_pack, engines)
        vulnerabilities = [
            self.registry.create_vulnerability(name)
            for name in request.enabled_vulnerabilities
        ]

        _safe_call_hook(self.lifecycle_hooks, "on_scan_start", request, vulnerabilities)
        run_error = None
        cleanup_error = None
        findings = []

        try:
            with self._engine_run_context(vulnerabilities, context):
                self._prepare_engines(request, engines)
                findings = self._run_vulnerabilities(vulnerabilities, context)
        except BaseException as exc:
            run_error = exc
            _safe_call_hook(self.lifecycle_hooks, "on_scan_error", exc)
        finally:
            _safe_call_hook(self.lifecycle_hooks, "on_cleanup_start")
            try:
                self._cleanup_engines(engines)
            except Exception as exc:
                cleanup_error = exc
                _safe_call_hook(self.lifecycle_hooks, "on_scan_error", exc)
            _safe_call_hook(self.lifecycle_hooks, "on_cleanup_end", cleanup_error)

        if cleanup_error is not None:
            if run_error is not None:
                cleanup_error.__context__ = run_error
                raise cleanup_error from run_error
            raise cleanup_error

        if run_error is not None:
            raise run_error

        self.last_run_stats = self._collect_run_stats(context, findings)
        _safe_call_hook(self.lifecycle_hooks, "on_scan_end", len(findings))
        return findings
