import os

import pytest

from agentguard.models import ToolCall
from agentguard.validator import ValidationError, validate_and_normalise


@pytest.fixture
def sandbox_root():
    return os.path.join("/tmp", "agentguard_test_sandbox")


def test_validator_blocks_path_traversal(sandbox_root):
    os.makedirs(sandbox_root, exist_ok=True)
    call = ToolCall("file.read", {"path": "notes/../finance/payroll.xlsx"}, "Read notes", "2024-01-01T00:00:00Z")
    with pytest.raises(ValidationError):
        validate_and_normalise(call, sandbox_root)


def test_validator_blocks_absolute_paths_outside_sandbox(sandbox_root):
    call = ToolCall("file.read", {"path": "/etc/passwd"}, "Read system file", "2024-01-01T00:00:01Z")
    with pytest.raises(ValidationError):
        validate_and_normalise(call, sandbox_root)


def test_validator_blocks_missing_and_wrong_type_params(sandbox_root):
    with pytest.raises(ValidationError):
        validate_and_normalise(ToolCall("file.read", {}, "Read missing path", "2024-01-01T00:00:02Z"), sandbox_root)

    with pytest.raises(ValidationError):
        validate_and_normalise(ToolCall("file.read", {"path": 42}, "Read numeric path", "2024-01-01T00:00:03Z"), sandbox_root)

    with pytest.raises(ValidationError):
        validate_and_normalise(ToolCall("email.send", {"to": ""}, "Empty address", "2024-01-01T00:00:04Z"), sandbox_root)


def test_validator_normalises_email_domain_and_paths(sandbox_root):
    call = ToolCall("email.send", {"to": "Student@Example.COM"}, "Send email", "2024-01-01T00:00:05Z")
    result = validate_and_normalise(call, sandbox_root)
    assert result.params["to"] == "Student@example.com"

    file_call = ToolCall("file.read", {"path": "notes/q3.txt"}, "Read notes", "2024-01-01T00:00:06Z")
    result = file_call
    result = validate_and_normalise(result, sandbox_root)
    assert os.path.isabs(result.params["path"])


def test_validator_blocks_symlink_escape(sandbox_root):
    target = os.path.join("/tmp", "agentguard_symlink_target")
    os.makedirs(target, exist_ok=True)
    os.makedirs(sandbox_root, exist_ok=True)
    link_path = os.path.join(sandbox_root, "escape")
    if os.path.lexists(link_path):
        os.unlink(link_path)
    os.symlink(target, link_path)

    call = ToolCall("file.read", {"path": "escape/secret.txt"}, "Read symlink escape", "2024-01-01T00:00:07Z")
    with pytest.raises(ValidationError):
        validate_and_normalise(call, sandbox_root)
