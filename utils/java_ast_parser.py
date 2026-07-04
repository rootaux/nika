import os
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava


def _node_text(source_bytes: bytes, node) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode(
        "utf-8", errors="ignore"
    )


def _normalize_lookup_name(name: str) -> str:
    return (name or "").split("(", 1)[0].strip()


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
        JAVA_LANGUAGE = Language(tsjava.language())
        parser = Parser(JAVA_LANGUAGE)
        root_node = parser.parse(source_bytes).root_node

        def find_name_line(node):
            if node.type in {"method_declaration", "constructor_declaration"}:
                name_node = node.child_by_field_name("name")
                if (
                    name_node is not None
                    and _node_text(source_bytes, name_node) == lookup_name
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
        
        # load java grammar
        JAVA_LANGUAGE = Language(tsjava.language())
        parser = Parser(JAVA_LANGUAGE)
        
        tree = parser.parse(source_bytes)
        root_node = tree.root_node
        
        def find_method_node(node, method_name):
            if node.type in {'method_declaration', 'constructor_declaration'}:
                name_node = node.child_by_field_name("name")
                if (
                    name_node is not None
                    and _node_text(source_bytes, name_node) == method_name
                ):
                    return node
            
            for child in node.children:
                result = find_method_node(child, method_name)
                if result:
                    return result
            return None
        

        def find_variables_node(node, method_name):
            if node.type == 'field_declaration':
                for child in node.children:
                    if child.type != 'variable_declarator':
                        continue
                    name_node = child.child_by_field_name("name")
                    if name_node is None and child.children:
                        name_node = child.children[0]
                    if (
                        name_node is not None
                        and _node_text(source_bytes, name_node) == method_name
                    ):
                        return node
            for child in node.children:
                result = find_variables_node(child, method_name)
                if result:
                    return result
            return None
        method_node = find_method_node(root_node, lookup_name)
        if not method_node:
            #Probably we are in wrong file or what we are looking for is a variable
            method_node = find_variables_node(root_node, lookup_name)
            if not method_node:
                return f"Method or Variable '{method_name}' not found in {file_path}"

        # method node will have annotations
        start_byte = method_node.start_byte
        end_byte = method_node.end_byte
        method_code = source_bytes[start_byte:end_byte].decode(
            "utf-8", errors="ignore"
        )
        return method_code.strip()
    except Exception as e:
        return f"Error extracting method with AST: {str(e)}"
