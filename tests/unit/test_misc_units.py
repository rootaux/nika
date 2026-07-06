from schema.config_schema import LLMConfig
from utils.java_ast_parser import extract_method_from_file, find_method_signature_line
from vulnerabilities.sensitive_logging.detectors import is_sensitive_log_snippet


_LOG_PII = """
class C {
  void f(String password, String name) {
    log.info("password=" + password);
  }
}
"""

_LOG_SAFE = """
class C {
  void f(String name) {
    log.info("hello " + name);
  }
}
"""

_NO_LOG = """
class C {
  void f(String password) {
    String x = "password=" + password;
  }
}
"""


def test_sensitive_log_flags_pii():
    assert is_sensitive_log_snippet(_LOG_PII, ["password", "secret"]) is True


def test_sensitive_log_ignores_non_pii():
    assert is_sensitive_log_snippet(_LOG_SAFE, ["password"]) is False


def test_sensitive_log_ignores_non_log_statements():
    assert is_sensitive_log_snippet(_NO_LOG, ["password"]) is False


def test_sensitive_log_empty_inputs():
    assert is_sensitive_log_snippet("", ["password"]) is False
    assert is_sensitive_log_snippet(_LOG_PII, []) is False

def test_signature_line_skips_annotations(tmp_path):
    src = tmp_path / "C.java"
    src.write_text(
        "class C {\n"
        "  @GetMapping(\"/x\")\n"
        "  @PreAuthorize(\"y\")\n"
        "  public String get(Long id) { return null; }\n"
        "}\n"
    )
    assert find_method_signature_line(str(src), "get") == 4


def test_signature_line_missing_method_returns_none(tmp_path):
    src = tmp_path / "C.java"
    src.write_text("class C { void a() {} }\n")
    assert find_method_signature_line(str(src), "nope") is None


def test_java_ast_parser_handles_non_ascii_before_methods(tmp_path):
    src = tmp_path / "C.java"
    src.write_text(
        "/* Copyright \u00a9 test */\n"
        "class C {\n"
        "  @GetMapping(\"/files\")\n"
        "  public String getFiles(String name) { return name; }\n"
        "}\n",
        encoding="utf-8",
    )

    body = extract_method_from_file(str(src), "getFiles")

    assert "public String getFiles" in body
    assert "return name" in body
    assert find_method_signature_line(str(src), "getFiles") == 4


def test_java_ast_parser_normalizes_signature_lookup(tmp_path):
    src = tmp_path / "C.java"
    src.write_text(
        "class C {\n"
        "  public String completed(String id) { return id; }\n"
        "}\n",
        encoding="utf-8",
    )

    body = extract_method_from_file(str(src), "completed(String)")

    assert "public String completed" in body


def test_java_ast_parser_extracts_constructors_and_fields(tmp_path):
    src = tmp_path / "Assignment7.java"
    src.write_text(
        "class Assignment7 {\n"
        "  private final String mailURL;\n"
        "  public Assignment7(String mailURL) { this.mailURL = mailURL; }\n"
        "}\n",
        encoding="utf-8",
    )

    constructor = extract_method_from_file(str(src), "Assignment7")
    field = extract_method_from_file(str(src), "mailURL")

    assert "public Assignment7" in constructor
    assert "private final String mailURL" in field


def test_java_ast_parser_class_context_includes_field_validation(tmp_path):
    src = tmp_path / "UserForm.java"
    src.write_text(
        "import jakarta.validation.constraints.Pattern;\n"
        "class UserForm {\n"
        "  @Pattern(regexp = \"[a-z0-9-]*\")\n"
        "  private String username;\n"
        "}\n",
        encoding="utf-8",
    )

    context = extract_method_from_file(str(src), "class")

    assert "Class context:" in context
    assert "@Pattern" in context
    assert "private String username" in context


def test_java_ast_parser_invalid_lookup_includes_class_context(tmp_path):
    src = tmp_path / "UserForm.java"
    src.write_text(
        "class UserForm {\n"
        "  @Size(min = 6)\n"
        "  private String username;\n"
        "}\n",
        encoding="utf-8",
    )

    context = extract_method_from_file(str(src), "<init>")

    assert "Class context:" in context
    assert "@Size" in context
    assert "private String username" in context


def test_java_ast_parser_constructor_signature_selects_overload(tmp_path):
    src = tmp_path / "User.java"
    src.write_text(
        "class User {\n"
        "  protected User() {}\n"
        "  public User(String username, String password) {\n"
        "    this.username = username;\n"
        "  }\n"
        "  private String username;\n"
        "}\n",
        encoding="utf-8",
    )

    constructor = extract_method_from_file(str(src), "User(String,String)")

    assert "public User(String username, String password)" in constructor
    assert "protected User() {}" not in constructor
