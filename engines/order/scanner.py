import logging
import re
import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import tree_sitter_java as ts_java
from tree_sitter import Language, Parser, Node
import yaml

JAVA_LANGUAGE = Language(ts_java.language())

@dataclass
class Rule:
    name: str
    description: str
    severity: str
    scope_function: str
    check: str
    filename: Optional[str] = ""
    sequence: list[str] = field(default_factory=list)
    chain_root: Optional[str] = ""
    ordered_calls: list[str] = field(default_factory=list)
    ignore_args: list[str] = field(default_factory=list)
    ignore_chain_root: list[str] = field(default_factory=list)


@dataclass
class Violation:
    rule: str
    severity: str
    file: str
    line: str
    message: str


    def __str__(self):
        tag = self.severity.upper()
        return f"{tag}: {self.file}:{self.line} - {self.message} (Rule: {self.rule})"

@dataclass
class ChainedCall:
    method_name: str
    arg_name: str
    line: int
    col: int

@dataclass
class SinkFinding:
    code: str
    file: str
    line_number: int
    line_number_end: int

def _parse_rule_file(path: str) -> list[Rule]:
    with open(path, 'r', encoding='utf-8') as f:
        rules_data = yaml.safe_load(f)
    if not rules_data or 'rules' not in rules_data:
        return []

    rules: list[Rule] = []
    for rule in rules_data['rules']:
        r = Rule(
            name=rule["name"],
            description=rule.get('description', ''),
            severity=rule.get('severity', ''),
            scope_function=rule["scope"]["function"],
            check=rule["check"],
            filename=rule.get('filename', ''),
        )
        if r.check == "call_sequence":
            r.sequence = rule["sequence"]
        elif r.check == "chain_order":
            r.chain_root = rule["chain_root"]
            r.ordered_calls = rule["ordered_calls"]
            r.ignore_args = rule.get("ignore_args", [])
            r.ignore_chain_root = rule.get("ignore_chain_root", [])
        else:
            logging.warning("Unknown check type %s in rule %s", r.check, r.name)
        rules.append(r)
    return rules


def _resolve_rules_path(rules_path: str | Path) -> Path:
    path = Path(rules_path).expanduser()
    if path.exists():
        return path.resolve()

    repo_root = Path(__file__).resolve().parent.parent
    candidate = (repo_root / path).resolve()
    if candidate.exists():
        return candidate

    raise FileNotFoundError(f"Rules path does not exist: {rules_path}")

def load_rules(rules_path: str | Path) -> list[Rule]:
    path = _resolve_rules_path(rules_path)
    if path.is_file():
        return _parse_rule_file(str(path))

    rules: list[Rule] = []
    for ext in ("*.yml", "*.yaml"):
        for file in sorted(path.glob(ext), key=lambda item: item.as_posix()):
            rules.extend(_parse_rule_file(str(file)))
    return rules

### Util functions for tree-sitter analysis

def _text(node: Node) -> str:
    return node.text.decode('utf-8') if node.text else ""

def _find_methods(root: Node) -> list[Node]:
    results: list[Node] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "method_declaration":
            results.append(node)
        stack.extend(node.children)
    return results

def _method_name(node: Node) -> str:
    for child in node.children:
        if child.type == "identifier":
            return _text(child)
    return ""


def _collect_invocations(node: Node) -> list[Node]:
    results: list[Node] = []
    stack = [node]
    while stack:
        node = stack.pop()
        if node.type == "method_invocation":
            results.append(node)
        stack.extend(node.children)
    return results


def _extract_arg_callable(invocation: Node) -> str:
    args_node = invocation.child_by_field_name("arguments")
    if args_node is None or args_node.named_child_count == 0:
        return ""
    first_arg = args_node.named_children[0]

    # handle method reference like ClassName::method or this::method
    if first_arg.type == "method_reference":
        named = first_arg.named_children
        if len(named) >= 2:
            qualifier = _text(named[0])
            method = _text(named[-1]) if named[-1].type == "identifier" else ""
            return f"{qualifier}::{method}" if method else qualifier
        elif len(named) == 1 and named[0].type == "identifier":
            return _text(named[0])
        return ""
    # plain identifier
    if first_arg.type == "identifier":
        return _text(first_arg)
    # handle lambda expressions like () -> method() or (arg) -> method(arg)
    if first_arg.type == "lambda_expression":
        body = first_arg.child_by_field_name("body")
        if body:
            invocations = _collect_invocations(body)
            if invocations:
                name_node = invocations[0].child_by_field_name("name")
                return _text(name_node) if name_node else ""
    # handle field access like ClassName.field or this.field
    if first_arg.type == "field_access":
        obj_node = first_arg.child_by_field_name("object")
        field_node = first_arg.child_by_field_name("field")
        if obj_node and field_node:
            return f"{_text(obj_node)}.{_text(field_node)}"
        return _text(field_node) if field_node else ""
    # variable holding handler
    if first_arg.type == "method_invocation":
        name_node = first_arg.child_by_field_name("name")
        return _text(name_node) if name_node else ""
    return _text(first_arg)


def _arg_matches(arg_name: str, pattern: str) -> bool:
    if arg_name == pattern:
        return True
    if "::" not in pattern and "." not in pattern:
        if "::" in arg_name:
            return arg_name.split("::")[-1] == pattern
        if "." in arg_name:
            return arg_name.split(".")[-1] == pattern
    if "*" in pattern or "?" in pattern:
        return fnmatch.fnmatch(arg_name, pattern)
    return False

def _get_first_arg_value(node: Node) -> str:
    node = node.child_by_field_name("arguments")
    if node is None or node.named_child_count == 0:
        return ""
    return _text(node.named_children[0])

def _should_ignore(arg_name: str, ignore_patterns: list[str]) -> bool:
    return any(_arg_matches(arg_name, pattern) for pattern in ignore_patterns)


def _find_matching_rule_entry(arg_name: str, ordered_calls: list[str]) -> str | None:
    for call in ordered_calls:
        if _arg_matches(arg_name, call):
            return call
    return None

def _unwind_chain(node: Node) -> list[ChainedCall]:
    links: list[ChainedCall] = []
    while node is not None and node.type == "method_invocation":
        name_node = node.child_by_field_name("name")
        if name_node:
            links.append(ChainedCall(
                method_name=_text(name_node),
                arg_name=_extract_arg_callable(node),
                line=node.start_point[0] + 1,
                col=node.start_point[1]
            ))

        obj = node.child_by_field_name("object")
        node = obj if obj is not None and obj.type == "method_invocation" else None
    links.reverse()
    return links


def _chain_receiver(node: Node) -> str:
    """
    Return the root receiver of the chain. For example, in a.b().c().d(), it will return "a". In a.b().c().d().e(), it will also return "a".
    """
    while True:
        obj = node.child_by_field_name("object")
        if obj is None:
            return ""
        if obj.type == "method_invocation":
            node = obj
            continue
        return _text(obj)

def _unwind_chain_header(node: Node) -> list[Node]:
    all_invocations = _collect_invocations(node)
    headers: list[Node] = []
    for invocation in all_invocations:
        parent = invocation.parent
        if parent is not None and parent.type == "method_invocation":
            if parent.child_by_field_name("object") == invocation:
                # skip if it's not the header of the chain
                continue
        headers.append(invocation)
    return headers


def _check_chain_order(method_node: Node, rule: Rule, filepath: str) -> list[Violation]:
    violations: list[Violation] = []
    root_parts = rule.chain_root.split(".")
    root_receiver = root_parts[0] if len(root_parts) == 2 else ""
    root_method = root_parts[-1]

    for head in _unwind_chain_header(method_node):
        chain = _unwind_chain(head)
        receiver = _chain_receiver(head)

        if not chain:
            continue
        if chain[0].method_name != root_method:
            continue
        if root_receiver and receiver != root_receiver:
            continue


        if rule.ignore_chain_root:
            root_node = head
            while root_node.type == "method_invocation":
                obj_node = root_node.child_by_field_name("object")
                if obj_node is not None and obj_node.type == "method_invocation":
                    root_node = obj_node
                else:
                    break
            root_receiver_arg = _get_first_arg_value(root_node)
            if any(fnmatch.fnmatch(root_receiver_arg, pattern) for pattern in rule.ignore_chain_root):
                continue

        filtered_chain: list[tuple[ChainedCall, str]] = []
        for call in chain:
            if not call.arg_name or _should_ignore(call.arg_name, rule.ignore_args):
                continue
            matched = _find_matching_rule_entry(call.arg_name, rule.ordered_calls)
            if matched:
                filtered_chain.append((call, matched))

        if not filtered_chain:
            continue

        arg_names = [c.arg_name for c in chain]
        ## check order 
        expected_idx = 0
        for call, matched_entry in filtered_chain:
            if expected_idx < len(rule.ordered_calls) and matched_entry == rule.ordered_calls[expected_idx]:
                expected_idx += 1
            else:
                violations.append(Violation(
                    rule=rule.name,
                    severity=rule.severity,
                    file=filepath,
                    line=call.line,
                    message=f"Expected call to {rule.ordered_calls[expected_idx]} but found {call.arg_name} in method chain. Expected order: {' -> '.join(rule.ordered_calls)}. Actual order: {', '.join(arg_names)}."
                ))
                # report only the first violation in the chain
                break
    return violations


def _check_call_sequence(method_node: Node, rule: Rule, filepath: str) -> list[Violation]:
    violations: list[Violation] = []
    invocations = _collect_invocations(method_node)

    filtered_invocations: list[tuple[str, int]] = []
    seq_set = set(rule.sequence)
    for invocation in invocations:
        name_node = invocation.child_by_field_name("name")
        if name_node and _text(name_node) in seq_set:
            filtered_invocations.append((_text(name_node), name_node.start_point[0] + 1))

    # sort by line number
    filtered_invocations.sort(key=lambda x: x[1])

    found_names = {name for name, _ in filtered_invocations}
    for required_call in rule.sequence:
        if required_call not in found_names:
            violations.append(Violation(
                rule=rule.name,
                severity=rule.severity,
                file=filepath,
                line=method_node.start_point[0] + 1,
                message=f"Missing required call to {required_call} in method."
            ))
    return violations


def analyze_file(filepath: str, rules: list[Rule]) -> list[Violation]:
    filepath = Path(filepath)
    source_code = filepath.read_bytes()
    parser = Parser(JAVA_LANGUAGE)
    tree = parser.parse(source_code)
    root = tree.root_node
    violations: list[Violation] = []
    methods = _find_methods(root)
    for method in methods:
        name = _method_name(method)
        for rule in rules:
            if rule.filename and not fnmatch.fnmatch(filepath.name, rule.filename):
                continue

            if not re.search(rule.scope_function, name):
                continue

            if rule.check == "call_sequence":
                violations.extend(_check_call_sequence(method, rule, str(filepath)))
            elif rule.check == "chain_order":
                violations.extend(_check_chain_order(method, rule, str(filepath)))
    return violations


def analyze_path(path: str | Path, rules: list[Rule]) -> list[Violation]:
    if not rules:
        logging.warning("No rules provided for analysis")
        return []
    all_violations: list[Violation] = []
    path = Path(path)
    logging.info("Analyzing %s for order scan vulnerabilities...", path)

    if path.is_file() and path.suffix == ".java":
        all_violations.extend(analyze_file(str(path), rules))
    elif path.is_dir():
        for file in sorted(path.rglob("*.java")):
            all_violations.extend(analyze_file(str(file), rules))
    return all_violations

class OrderAnalyzer:
    def __init__(self, rules_path: str):
        self.rules = load_rules(rules_path)

    def analyze(self, path: str | Path) -> list[Violation]:
        all_violations =  analyze_path(path, self.rules)
        logging.info("Total violations found: %d", len(all_violations))
        sink_findings = []
        for violation in all_violations:
            sink_findings.append({
                "code": violation.message,
                "file": violation.file,
                "line_number": violation.line,
                "line_number_end": violation.line,
            })
        return sink_findings
