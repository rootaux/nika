import logging
from typing import Optional

from tree_sitter import Language, Parser
import tree_sitter_java as tsjava


def _node_text(source_bytes: bytes, node) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')

def _normalize(text: str) -> str:
    import re
    if not text:
        return ""
    t = re.sub(r"\b(this|super)\.\b", "", text)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def locate_call_line_in_method(source: str, method_name: str, callee_snippet: str) -> Optional[int]:
    """Locate the line number of a call within a given enclosing method by comparing normalized code.
    Returns 1-based line number or None if not found.
    """
    logging.info("Locating call line in method: %s", method_name)
    logging.info("Callee snippet: %s", callee_snippet)
    logging.info("Source length: %d", len(source))
    JAVA_LANGUAGE = Language(tsjava.language())
    parser = Parser(JAVA_LANGUAGE)
    source_bytes = source.encode('utf-8', errors='ignore')
    tree = parser.parse(source_bytes)
    # Ensure language is initialized for Query
    lang = JAVA_LANGUAGE
    # Query for method declarations and method invocations
    from tree_sitter import Query, QueryCursor
    q = Query(lang, r"""
        (method_declaration
            name: (identifier) @mname
        ) @mdecl

        (method_invocation
            name: (identifier) @cname
            arguments: (argument_list) @cargs
        ) @call
    """)
    cursor = QueryCursor(q)
    captures = []
    for capname, node in cursor.captures(tree.root_node).items():
        captures.append((node, capname))

    # Collect method ranges for the given method_name
    method_ranges = []
    for node, capname in captures:
        if capname == 'mname':
            for n in node:
                name_text = _node_text(source_bytes, n)
                if name_text == method_name:
                    mdecl = n.parent
                    if mdecl is not None:
                        method_ranges.append((mdecl.start_point[0], mdecl.end_point[0]))  # rows (0-based)

    if not method_ranges:
        # fallback: search entire file
        method_ranges = [(-1, 10**9)]

    target_norm = _normalize(callee_snippet)
    if not target_norm:
        return None

    # Collect call invocations within method ranges and compare normalized text
    for nodes, capname in captures:
        if capname == 'call':
            for node in nodes:
                call_node = node
                row = call_node.start_point[0]
                # Check if within any method range
                if any(start <= row <= end for start, end in method_ranges):
                    call_text = _node_text(source_bytes, call_node)
                    if _normalize(call_text) == target_norm:
                        return row + 1  # 1-based
    return None
