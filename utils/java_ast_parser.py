import os
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

_CLASS_CONTEXT_LOOKUPS = {"*", "class", "<class>"}
_CONSTRUCTOR_LOOKUPS = {"<init>", "constructor", "constructors"}
_TYPE_DECLARATIONS = {
    "annotation_type_declaration",
    "class_declaration",
    "enum_declaration",
    "interface_declaration",
    "record_declaration",
}


def _node_text(source_bytes: bytes, node) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode(
        "utf-8", errors="ignore"
    )


def _normalize_lookup_name(name: str) -> str:
    return (name or "").split("(", 1)[0].strip()


def _lookup_arity(name: str) -> int | None:
    if "(" not in (name or "") or ")" not in (name or ""):
        return None
    inside = name[name.find("(") + 1:name.rfind(")")].strip()
    if not inside:
        return 0
    return len([part for part in inside.split(",") if part.strip()])


def _java_root_node(source_bytes: bytes):
    java_language = Language(tsjava.language())
    parser = Parser(java_language)
    return parser.parse(source_bytes).root_node


def _parameter_count(node) -> int | None:
    params = node.child_by_field_name("parameters")
    if params is None:
        return None
    return len(
        [
            child
            for child in params.children
            if child.type in {"formal_parameter", "spread_parameter"}
        ]
    )


def _find_first_type_node(node):
    if node.type in _TYPE_DECLARATIONS:
        return node
    for child in node.children:
        result = _find_first_type_node(child)
        if result:
            return result
    return None


def _find_nodes(node, node_type: str) -> list:
    results = []
    if node.type == node_type:
        results.append(node)
    for child in node.children:
        results.extend(_find_nodes(child, node_type))
    return results


def _declaration_header(source_bytes: bytes, node) -> str:
    body = node.child_by_field_name("body")
    if body is not None:
        text = source_bytes[node.start_byte:body.start_byte].decode(
            "utf-8", errors="ignore"
        ).strip()
        return f"{text} {{...}}"
    return _node_text(source_bytes, node).strip()


def _class_context(source_bytes: bytes, root_node) -> str:
    type_node = _find_first_type_node(root_node)
    if type_node is None:
        return ""

    body = type_node.child_by_field_name("body")
    declaration = _declaration_header(source_bytes, type_node)
    search_root = body or type_node
    fields = [_node_text(source_bytes, node).strip() for node in _find_nodes(search_root, "field_declaration")]
    constructors = [
        _declaration_header(source_bytes, node)
        for node in _find_nodes(search_root, "constructor_declaration")
    ]
    methods = [
        _declaration_header(source_bytes, node)
        for node in _find_nodes(search_root, "method_declaration")
    ]

    sections = ["Class context:", declaration]
    if fields:
        sections.extend(["", "Fields:", *fields])
    if constructors:
        sections.extend(["", "Constructors:", *constructors])
    if methods:
        sections.extend(["", "Methods:", *methods])
    return "\n".join(sections).strip()


def _constructor_context(source_bytes: bytes, root_node) -> str:
    constructors = [
        _node_text(source_bytes, node).strip()
        for node in _find_nodes(root_node, "constructor_declaration")
    ]
    if constructors:
        return "\n\n".join(["Constructors:", *constructors]).strip()
    return _class_context(source_bytes, root_node)


def find_method_signature_line(
    file_path: str,
    method_name: str,
    append_path: str = None,
) -> int | None:
    """Return the 1-based line of a method's declaration."""
    try:
        if not os.path.exists(file_path):
            file_path = os.path.join(append_path or "", file_path)
        if not os.path.exists(file_path):
            return None

        if append_path:
            resolved = os.path.realpath(file_path)
            project_root = os.path.realpath(append_path)
            if not resolved.startswith(project_root + os.sep) and resolved != project_root:
                return None

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source_code = f.read()

        source_bytes = source_code.encode("utf-8")
        lookup_name = _normalize_lookup_name(method_name)
        lookup_arity = _lookup_arity(method_name)
        root_node = _java_root_node(source_bytes)

        def find_name_line(node):
            if node.type in {"method_declaration", "constructor_declaration"}:
                name_node = node.child_by_field_name("name")
                if (
                    name_node is not None
                    and _node_text(source_bytes, name_node) == lookup_name
                    and (
                        lookup_arity is None
                        or _parameter_count(node) == lookup_arity
                    )
                ):
                    return name_node.start_point[0] + 1
            for child in node.children:
                result = find_name_line(child)
                if result:
                    return result
            return None

        return find_name_line(root_node)
    except Exception:
        return None


def extract_method_from_file(
    file_path: str,
    method_name: str,
    append_path: str = None,
) -> str:
    try:
        if not os.path.exists(file_path):
            file_path = os.path.join(append_path, file_path)
        if not os.path.exists(file_path):
            return f"File not found: {file_path}"

        # Guard against path traversal
        if append_path:
            resolved = os.path.realpath(file_path)
            project_root = os.path.realpath(append_path)
            if not resolved.startswith(project_root + os.sep) and resolved != project_root:
                return "Access denied: path outside project"

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source_code = f.read()
        source_bytes = source_code.encode("utf-8")
        lookup_name = _normalize_lookup_name(method_name)
        lookup_arity = _lookup_arity(method_name)
        
        root_node = _java_root_node(source_bytes)

        if lookup_name in _CLASS_CONTEXT_LOOKUPS:
            context = _class_context(source_bytes, root_node)
            return context or f"Class context not found in {file_path}"

        if lookup_name in _CONSTRUCTOR_LOOKUPS:
            context = _constructor_context(source_bytes, root_node)
            return context or f"Constructor not found in {file_path}"
        
        def find_method_node(node, lookup_name):
            candidates = []

            def visit(current):
                if current.type in {'method_declaration', 'constructor_declaration'}:
                    name_node = current.child_by_field_name("name")
                    if (
                        name_node is not None
                        and _node_text(source_bytes, name_node) == lookup_name
                    ):
                        if lookup_arity is None or _parameter_count(current) == lookup_arity:
                            return current
                        candidates.append(current)

                for child in current.children:
                    result = visit(child)
                    if result:
                        return result
                return None

            return visit(node) or (candidates[0] if candidates else None)
        

        def find_variables_node(node, lookup_name):
            if node.type == 'field_declaration':
                for child in node.children:
                    if child.type != 'variable_declarator':
                        continue
                    name_node = child.child_by_field_name("name")
                    if name_node is None and child.children:
                        name_node = child.children[0]
                    if (
                        name_node is not None
                        and _node_text(source_bytes, name_node) == lookup_name
                    ):
                        return node
            for child in node.children:
                result = find_variables_node(child, lookup_name)
                if result:
                    return result
            return None
        method_node = find_method_node(root_node, lookup_name)
        if not method_node:
            #Probably we are in wrong file or what we are looking for is a variable
            method_node = find_variables_node(root_node, lookup_name)
            if not method_node:
                not_found = f"Method or Variable '{method_name}' not found in {file_path}"
                context = _class_context(source_bytes, root_node)
                return f"{not_found}\n\n{context}" if context else not_found

        # method node will have annotations
        start_byte = method_node.start_byte
        end_byte = method_node.end_byte
        method_code = source_bytes[start_byte:end_byte].decode(
            "utf-8", errors="ignore"
        )
        return method_code.strip()
    except Exception as e:
        return f"Error extracting method with AST: {str(e)}"
