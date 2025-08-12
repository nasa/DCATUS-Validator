import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

import rfc3987
from jsonschema import Draft7Validator, FormatChecker
from jsonschema.exceptions import ValidationError, best_match


def _path_str(path_iterable: Sequence[str | int]) -> str:
    """
    Convert a jsonschema absolute_path into a compact, JSONPath-like string.

    :param path_iterable: A list of path components.
    """
    parts = []
    for p in path_iterable:
        if isinstance(p, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{p}]"
            else:
                parts.append(f"[{p}]")
        else:
            parts.append(str(p))
    return ".".join(parts) if parts else ""


def _pick_best_suberror(context: list[ValidationError]) -> ValidationError | None:
    """
    From a list of sub-errors (e.context), choose the most specific one.

    :param context: A list of sub-errors.
    """
    if not context:
        return None
    best = None
    best_depth = -1
    for se in context:
        depth = len(list(se.absolute_schema_path))
        if depth > best_depth:
            best = se
            best_depth = depth
    return best


def validate_dcat(datasets: list[dict]) -> list[dict]:
    """
    Validate datasets against the GSA DCAT schema.

    :param datasets: A list of datasets to validate.
    :raises SchemaError: If the schema is invalid.
    :return: A list containing invalid datasets.
    """
    invalid_datasets = []
    schemas_folder = Path(__file__).resolve().parent / "schemas"
    schema_path = schemas_folder / "gsa-dcat-v7.json"
    format_checker = FormatChecker()

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    Draft7Validator.check_schema(schema)
    validator = Draft7Validator(schema, format_checker=format_checker)

    for dataset in datasets:
        error_messages = []

        errors = sorted(
            validator.iter_errors(dataset),
            key=lambda e: (tuple(e.absolute_path), tuple(e.absolute_schema_path)),
        )

        for err in errors:
            path = _path_str(err.absolute_path)
            base_msg = err.message

            if err.validator in ("oneOf", "anyOf", "allOf") and err.context:
                sub = _pick_best_suberror(err.context)
                if sub is not None:
                    sub_path = _path_str(sub.absolute_path) or path
                    sub_msg = sub.message
                    if sub_path and sub_path != path:
                        error_messages.append(f"{sub_path}: {sub_msg}")
                    else:
                        error_messages.append(f"{path}: {sub_msg}" if path else sub_msg)
                    continue

            if path:
                error_messages.append(f"{path}: {base_msg}")
            else:
                error_messages.append(base_msg)

        if error_messages:
            invalid_datasets.append(
                {
                    "title": dataset.get("title", "Unknown Title"),
                    "errors": sorted(set(error_messages)),
                }
            )

    return invalid_datasets


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Validate a DCAT-US JSON file against the GSA schema."
    )
    parser.add_argument("filepath", help="The path to the DCAT JSON file to validate.")

    args = parser.parse_args()

    try:
        with open(args.filepath, "r", encoding="utf-8") as f:
            datasets_to_validate = json.load(f)
            datasets_to_validate = datasets_to_validate.get("dataset", [])
    except FileNotFoundError:
        logging.error(f"Error: The file '{args.filepath}' was not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Error: Could not decode JSON from the file '{args.filepath}'.")
        sys.exit(1)

    logging.info(f"Validating {len(datasets_to_validate)} datasets...")
    result = validate_dcat(datasets_to_validate)
    logging.info("Validation complete.")

    if not result:
        logging.info("All datasets are valid.")
    else:
        logging.info("Invalid datasets found:")
        logging.info(f"Found {len(result)} invalid datasets.")

        with open("invalid_datasets.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
