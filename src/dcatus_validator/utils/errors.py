from typing import Any, Callable, Iterable, Sequence

from jsonschema.exceptions import ValidationError


def _unique(items: Iterable[str]) -> list[str]:
    """
    Drop duplicates while preserving first-seen order.

    ``anyOf`` branches often produce identical summaries; this keeps one of each.

    :param items: The strings to deduplicate.
    :return: The unique strings in their original order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _describe_composition(error: ValidationError) -> str:
    """
    Describe an ``anyOf``/``oneOf``/``allOf`` failure via its sub-errors.

    A nullable field declared as ``anyOf: [<type>, null]`` reads as
    "is not null and <real problem>".

    :param error: A composition error with a populated ``context``.
    :return: A human-readable description.
    """
    if all(_is_null_type_error(sub) for sub in error.context):
        return "is not null and does not match any allowed type"

    has_null_alternative = any(_is_null_type_error(sub) for sub in error.context)

    summaries: list[str] = []
    for sub_error in _find_meaningful_errors(error.context):
        description = _describe_error(sub_error)
        if not description:
            continue
        suffix = _describe_relative_path(sub_error, error.absolute_path).lstrip(".")
        summaries.append(f"{suffix}: {description}" if suffix else description)

    unique = _unique(summaries)
    if not unique:
        return error.message

    if len(unique) == 1:
        return f"is not null and {unique[0]}" if has_null_alternative else unique[0]

    joined = "; ".join(unique)
    if has_null_alternative:
        return f"is not null and does not match alternatives: {joined}"
    return f"does not match any alternative: {joined}"


def _describe_ref(error: ValidationError) -> str | None:
    """
    Describe a ``$ref`` wrapper failure by naming the expected class.

    :param error: An error whose schema is a ``$ref``.
    :return: A description, or None when the ref yields nothing useful and the
        caller should fall back to keyword handling.
    """
    class_name = _extract_schema_name(error.schema)

    if error.context:
        unique = _unique(
            description
            for sub_error in _find_meaningful_errors(error.context)
            if (description := _describe_error(sub_error))
        )
        if unique:
            joined = "; ".join(unique)
            return (
                f"does not conform to {class_name}: {joined}" if class_name else joined
            )

    return f"does not conform to {class_name}" if class_name else None


def _describe_required(error: ValidationError) -> str:
    if "is a required property" in error.message:
        field = error.message.split("'")[1]
        return f"missing required field '{field}'"
    return error.message


def _describe_type(error: ValidationError) -> str:
    expected = error.validator_value
    if isinstance(expected, list):
        expected = " or ".join(str(item) for item in expected)
    return f"expected type '{expected}'"


def _describe_enum(error: ValidationError) -> str:
    return f"value not in allowed values: {error.validator_value}"


def _describe_pattern(error: ValidationError) -> str:
    return f"does not match pattern '{error.validator_value}'"


def _describe_format(error: ValidationError) -> str:
    return f"invalid format, expected '{error.validator_value}'"


_KEYWORD_DESCRIBERS: dict[str, Callable[[ValidationError], str]] = {
    "required": _describe_required,
    "type": _describe_type,
    "enum": _describe_enum,
    "pattern": _describe_pattern,
    "format": _describe_format,
}


def _format_path(path: Sequence[str | int]) -> str:
    """
    Format a jsonschema path as a readable string like ``subject[0].inScheme``.

    :param path: An iterable of path components.
    :return: A compact JSONPath-like string, or ``(root)`` when empty.
    """
    parts: list[str] = []
    for component in path:
        if isinstance(component, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{component}]"
            else:
                parts.append(f"[{component}]")
        else:
            parts.append(str(component))
    return ".".join(parts) if parts else "(root)"


def _is_null_type_error(error: ValidationError) -> bool:
    """
    Check whether an error only complains that a value is not ``null``.

    :param error: The error to inspect.
    :return: True when the error is a ``type: null`` failure.
    """
    return error.validator == "type" and error.validator_value == "null"


def _find_meaningful_errors(errors: Iterable[ValidationError]) -> list[ValidationError]:
    """
    Filter sub-errors down to the informative ones, skipping ``type: null`` noise.

    :param errors: The sub-errors of an ``anyOf``/``oneOf``/``allOf`` failure.
    :return: The non-null-type errors, or all errors when every one is null-type.
    """
    error_list = list(errors)
    meaningful = [error for error in error_list if not _is_null_type_error(error)]
    return meaningful if meaningful else error_list


def _extract_schema_name(schema: Any) -> str | None:
    """
    Derive a human-readable class name from a schema definition.

    :param schema: A schema fragment, typically ``error.schema``.
    :return: The class name, or None when one cannot be determined.
    """
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if isinstance(ref, str) and ref:
            name = ref.rstrip("/#").rpartition("/")[2]
            if name.endswith(".json"):
                name = name[: -len(".json")]
            return name.replace("-", " ").replace("_", " ").title().replace(" ", "")
        title = schema.get("title")
        if isinstance(title, str) and title:
            return title
    return None


def _describe_relative_path(
    error: ValidationError, base_path: Sequence[str | int]
) -> str:
    """
    Describe how far below a parent error a sub-error occurred.

    :param error: The sub-error.
    :param base_path: The absolute path of the parent error.
    :return: A dotted suffix such as ``.inScheme``, or an empty string.
    """
    absolute = list(error.absolute_path)
    base = list(base_path)
    if len(absolute) <= len(base) or absolute[: len(base)] != base:
        return ""
    suffix = _format_path(absolute[len(base) :])
    return "" if suffix == "(root)" else f".{suffix}"


def _describe_error(error: ValidationError) -> str:
    """
    Describe a validation error without any path prefix.

    Recurses through ``anyOf``/``oneOf``/``allOf`` contexts and ``$ref`` wrappers so
    the reported problem is the underlying one rather than the container failure.

    :param error: The error to describe.
    :return: A human-readable description with no leading path.
    """
    if error.validator in ("anyOf", "oneOf", "allOf") and error.context:
        return _describe_composition(error)

    if isinstance(error.schema, dict) and "$ref" in error.schema:
        description = _describe_ref(error)
        if description:
            return description

    describer = _KEYWORD_DESCRIBERS.get(str(error.validator))
    return describer(error) if describer else error.message


def format_error(error: ValidationError, prefix: str = "") -> str:
    """
    Format a validation error as ``<path>: <description>``, prepending the path once.

    :param error: The error to format.
    :param prefix: An indentation prefix applied to the whole line.
    :return: A single-line, human-readable error string.
    """
    return f"{prefix}{_format_path(error.absolute_path)}: {_describe_error(error)}"
