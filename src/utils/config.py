from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(",")]
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    try:
        import yaml  # type: ignore

        with path.open("r", encoding="utf-8") as file:
            loaded = yaml.safe_load(file) or {}
        return loaded
    except Exception:
        return _load_yaml_fallback(path)


def _strip_comment(line: str) -> str:
    in_quote = False
    quote_char = ""
    result = []
    for char in line:
        if char in {"'", '"'}:
            if not in_quote:
                in_quote = True
                quote_char = char
            elif quote_char == char:
                in_quote = False
        if char == "#" and not in_quote:
            break
        result.append(char)
    return "".join(result).rstrip()


def _load_yaml_fallback(path: Path) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = _strip_comment(raw_line)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip()
        value = value.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(value)
    return root


def load_config_dir(config_dir: str | Path) -> dict[str, dict[str, Any]]:
    config_dir = Path(config_dir)
    configs: dict[str, dict[str, Any]] = {}
    for path in config_dir.glob("*.yaml"):
        configs[path.stem] = load_yaml(path)
    return configs
