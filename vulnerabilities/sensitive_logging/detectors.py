from tree_sitter import Language, Parser
import tree_sitter_java as tsjava


def _node_text(node):
    return node.text.decode("utf-8")


def _is_log_invocation(node):
    if node.type != "method_invocation":
        return False

    object_node = node.child_by_field_name("object")
    if object_node is None:
        return False

    receiver = _node_text(object_node).split(".")[-1].lower()
    return receiver in {"log", "logger"}


def _collect_method_invocations(node, results):
    if node.type == "method_invocation":
        results.append(_node_text(node))

    for child in node.children:
        _collect_method_invocations(child, results)


def _collect_identifiers(node, results):
    if node.type == "identifier":
        results.append(_node_text(node))

    for child in node.children:
        _collect_identifiers(child, results)


def _extract_log_arg_tokens(node):
    matches = []
    if _is_log_invocation(node):
        argument_list = node.child_by_field_name("arguments")
        if argument_list is None:
            return matches
        for argument in argument_list.named_children:
            _collect_method_invocations(argument, matches)
            _collect_identifiers(argument, matches)
        return matches
    for child in node.children:
        matches.extend(_extract_log_arg_tokens(child))
    return matches


def is_sensitive_log_snippet(source_code: str, pii_keywords: list[str]) -> bool:
    if not source_code or not pii_keywords:
        return False

    java_language = Language(tsjava.language())
    parser = Parser(java_language)
    tree = parser.parse(source_code.encode("utf-8"))

    log_data = []
    for child in tree.root_node.children:
        log_data.extend(_extract_log_arg_tokens(child))

    return any(
        keyword.lower() in data.lower()
        for data in log_data
        for keyword in pii_keywords
    )
