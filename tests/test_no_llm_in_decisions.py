import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _module_has_forbidden_imports(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    module = ast.parse(text, filename=str(path))
    forbidden = {"llm", "agentguard.llm", "anthropic", "openai"}
    found = []
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            for name in node.names:
                if name.name in forbidden:
                    found.append(name.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module in forbidden:
                found.append(node.module)
    return found


def test_guardrail_modules_do_not_import_llm_clients():
    targets = [
        ROOT / "agentguard" / "checkpoint.py",
        ROOT / "agentguard" / "policy_engine.py",
        ROOT / "agentguard" / "validator.py",
    ]
    for path in targets:
        assert _module_has_forbidden_imports(path) == [], f"Forbidden LLM import found in {path}"
