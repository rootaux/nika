import os
from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

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
        
        # load java grammar
        JAVA_LANGUAGE = Language(tsjava.language())
        parser = Parser(JAVA_LANGUAGE)
        
        tree = parser.parse(bytes(source_code, "utf8"))
        root_node = tree.root_node
        
        def find_method_node(node, method_name):
            if node.type == 'method_declaration':
                for child in node.children:
                    if child.type == 'identifier' and source_code[child.start_byte:child.end_byte] == method_name:
                        return node
            
            for child in node.children:
                result = find_method_node(child, method_name)
                if result:
                    return result
            return None
        

        def find_variables_node(node, method_name):
            if node.type == 'field_declaration':
                for child in node.children:
                    if child.type == 'variable_declarator' and source_code[child.children[0].start_byte:child.children[0].end_byte] == method_name:
                        return node
            for child in node.children:
                result = find_variables_node(child, method_name)
                if result:
                    return result
            return None
        method_node = find_method_node(root_node, method_name)
        if not method_node:
            #Probably we are in wrong file or what we are looking for is a variable
            method_node = find_variables_node(root_node, method_name)
            if not method_node:
                return f"Method or Variable '{method_name}' not found in {file_path}"

        # method node will have annotations
        start_byte = method_node.start_byte
        end_byte = method_node.end_byte
        method_code = source_code[start_byte:end_byte]
        return method_code.strip()
    except Exception as e:
        return f"Error extracting method with AST: {str(e)}"
