from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOWED_RULE_TYPES = {
    "file_exists",
    "json_parseable",
    "json_schema",
    "command_exit_code",
    "text_contains",
    "text_not_contains",
}


@dataclass(frozen=True)
class ContractValidationResult:
    ok: bool
    error: str | None = None
    done_when: list[dict[str, Any]] | None = None

def validate_done_when(done_when: Any) -> ContractValidationResult:
    if done_when is None:
        return ContractValidationResult(ok=True, done_when=[])
    if not isinstance(done_when, list):
        return ContractValidationResult(ok=False, error="done_when must be an array.")
    normalized: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(done_when):
        if not isinstance(raw_rule, dict):
            return ContractValidationResult(ok=False, error=f"done_when[{index}] must be an object.")
        if set(raw_rule.keys()) != {"type", "args"}:
            return ContractValidationResult(
                ok=False,
                error=f"done_when[{index}] must contain exactly 'type' and 'args'.",
            )
        rule_type = raw_rule.get("type")
        args = raw_rule.get("args")
        if not isinstance(rule_type, str) or rule_type not in ALLOWED_RULE_TYPES:
            return ContractValidationResult(
                ok=False,
                error=(
                    f"done_when[{index}].type must be one of: "
                    + ", ".join(sorted(ALLOWED_RULE_TYPES))
                ),
            )
        if not isinstance(args, dict):
            return ContractValidationResult(ok=False, error=f"done_when[{index}].args must be an object.")
        err = _validate_rule_args(index=index, rule_type=rule_type, args=args)
        if err:
            return ContractValidationResult(ok=False, error=err)
        normalized.append({"type": rule_type, "args": dict(args)})
    return ContractValidationResult(ok=True, done_when=normalized)


def _validate_rule_args(*, index: int, rule_type: str, args: dict[str, Any]) -> str | None:
    if rule_type in {"file_exists", "json_parseable"}:
        if not isinstance(args.get("path"), str) or not str(args.get("path")).strip():
            return f"done_when[{index}].args.path is required for {rule_type}."
        return None
    if rule_type == "json_schema":
        path = args.get("path")
        has_inline_schema = isinstance(args.get("schema"), dict)
        has_schema_path = isinstance(args.get("schema_path"), str) and bool(str(args.get("schema_path")).strip())
        if not isinstance(path, str) or not path.strip():
            return f"done_when[{index}].args.path is required for json_schema."
        if not (has_inline_schema or has_schema_path):
            return f"done_when[{index}] json_schema needs args.schema or args.schema_path."
        return None
    if rule_type == "command_exit_code":
        if not isinstance(args.get("command"), str) or not str(args.get("command")).strip():
            return f"done_when[{index}].args.command is required for command_exit_code."
        if "exit_code" in args and not isinstance(args.get("exit_code"), int):
            return f"done_when[{index}].args.exit_code must be integer when provided."
        return None
    if rule_type in {"text_contains", "text_not_contains"}:
        path = args.get("path")
        terms = args.get("terms")
        if not isinstance(path, str) or not path.strip():
            return f"done_when[{index}].args.path is required for {rule_type}."
        if not isinstance(terms, list) or not terms:
            return f"done_when[{index}].args.terms must be a non-empty array for {rule_type}."
        for i, t in enumerate(terms):
            if not isinstance(t, str) or not t.strip():
                return f"done_when[{index}].args.terms[{i}] must be non-empty string."
        return None
    return f"done_when[{index}] has unsupported type: {rule_type}"
