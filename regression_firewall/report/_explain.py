from __future__ import annotations

WHY_IT_MATTERS = {
    "status_changed": (
        "Clients branch on status codes; a flipped status silently changes "
        "error handling for every existing caller."
    ),
    "field_removed": (
        "Existing consumers may read this field; removing it breaks them at "
        "runtime, not at compile time."
    ),
    "field_added": (
        "Additive change; usually safe, but may leak internal data or bloat "
        "payloads."
    ),
    "field_type_changed": (
        "Callers expecting the previous type (number vs string) may crash or "
        "mis-parse the value."
    ),
    "response_shape_changed": (
        "The overall payload shape changed; generic consumers (deserializers, "
        "codegen clients) may fail entirely."
    ),
    "content_type_changed": (
        "Clients select parsers by content-type; a flip can turn working "
        "integrations into parse errors."
    ),
    "header_changed": (
        "Headers carry caching/auth/contract metadata; verify the new value "
        "is intentional."
    ),
    "cookie_changed": (
        "Cookie changes can affect sessions, CSRF protection, and caching."
    ),
    "value_changed": (
        "The value at this location changed; confirm it is data-driven noise "
        "and not new behavior."
    ),
    "list_size_changed": (
        "The number of items changed; could be data drift or missing records."
    ),
    "exit_code_changed": (
        "Scripts, CI jobs, and supervisors branch on exit codes; a flip can "
        "fail pipelines or mask failures."
    ),
    "stdout_changed": (
        "Tooling that parses this output may depend on the previous text."
    ),
    "stderr_changed": (
        "New error output can indicate hidden failures even when the exit "
        "code is unchanged."
    ),
    "file_created": (
        "A new file appeared as a side effect; check for pollution of user "
        "directories or repo state."
    ),
    "file_deleted": (
        "A previously generated file is gone; anything depending on it will "
        "fail."
    ),
    "file_modified": (
        "A generated file's content changed; confirm the new content is "
        "intended."
    ),
    "symbol_removed": (
        "Hard backward-compatibility break: every caller importing this "
        "symbol will fail with an ImportError/AttributeError."
    ),
    "symbol_added": (
        "Purely additive; no existing caller can break."
    ),
    "signature_changed": (
        "Callers using the previous signature (positional order, defaults, "
        "keyword names) may break."
    ),
    "export_changed": (
        "The package's declared public surface (__all__) changed; star "
        "imports and tooling may behave differently."
    ),
    "capture_error": (
        "The probe could not reach the subject at all — the surface may be "
        "down, hanging, or misconfigured."
    ),
}

RECOMMENDED_ACTIONS = {
    "status_changed": "Restore the previous HTTP status unless this API contract change is intentional.",
    "field_removed": "Restore the removed field, or agree a deprecation window with consumers.",
    "field_added": "Confirm the new field is meant to be public and contains no sensitive data.",
    "field_type_changed": "Restore the previous type or version the API for existing consumers.",
    "response_shape_changed": "Restore the previous payload shape or ship a new API version.",
    "content_type_changed": "Restore the previous content-type or update all consumers deliberately.",
    "header_changed": "Verify the header change is intentional and does not affect caching/auth.",
    "cookie_changed": "Verify session/CSRF behavior still holds with the new cookie values.",
    "value_changed": "Confirm the new value is correct and not accidental output drift.",
    "list_size_changed": "Verify the item count change is data, not dropped behavior.",
    "exit_code_changed": "Restore the previous exit code unless callers were updated for it.",
    "stdout_changed": "Confirm the new output text is intended and parsers are unaffected.",
    "stderr_changed": "Investigate why stderr output appeared or changed.",
    "file_created": "Confirm the new file belongs where it is written (and is git-ignored if local).",
    "file_deleted": "Restore the generated file or update its consumers.",
    "file_modified": "Confirm the new file content is intended.",
    "symbol_removed": "Restore the removed symbol or publish a deprecation before removing it.",
    "symbol_added": "No action needed; additive change.",
    "signature_changed": "Keep the old call signature working or add the parameter as optional.",
    "export_changed": "Verify __all__ changes match the intended public surface.",
    "capture_error": "Check why the surface became unreachable (crash, hang, port, config).",
}

DEFAULT_ACTION = "Review the change and restore previous behavior unless it is intentional."


def why_it_matters(category: str) -> str:
    return WHY_IT_MATTERS.get(category, "The behavior at this location changed.")


def recommended_action(category: str) -> str:
    return RECOMMENDED_ACTIONS.get(category, DEFAULT_ACTION)
