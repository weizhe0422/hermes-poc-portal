"""Secret Redaction 測試（RT-13、NF-03；RUNTIME-013 forbidden pattern）。"""

from app.redaction.redactor import MASK, redact_line, redact_lines


def test_test_secret_pattern_is_masked():
    # E2E 固定假 Secret（docs/04：報告中只能出現遮蔽值）
    line = redact_line("api_key=TEST_SECRET_123456")
    assert "TEST_SECRET_123456" not in line
    assert MASK in line


def test_bearer_token_is_masked():
    line = redact_line("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc")
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in line


def test_key_value_secrets_are_masked_but_keys_remain():
    for key in ("password", "api-key", "token", "secret", "credential"):
        line = redact_line(f"{key}=super-sensitive-value")
        assert "super-sensitive-value" not in line, key
        assert key in line, "key 名稱應保留以利除錯"


def test_private_key_line_fully_masked():
    line = redact_line("-----BEGIN RSA PRIVATE KEY----- MIIEow...")
    assert line == MASK


def test_sk_style_api_key_masked():
    line = redact_line("calling llm with sk-abcdef1234567890")
    assert "sk-abcdef1234567890" not in line


def test_normal_lines_unchanged():
    line = "INFO starting hermes agent on port 8000"
    assert redact_line(line) == line


def test_redact_lines_preserves_order_and_length():
    lines = ["a", "password=x", "c"]
    result = redact_lines(lines)
    assert len(result) == 3
    assert result[0] == "a" and result[2] == "c"
    assert "password" in result[1] and "=x" not in result[1]
