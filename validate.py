import argparse
import json
import logging
import sys
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker, SchemaError, ValidationError


def validate_dcat(datasets: list[dict]) -> list[dict]:
    """
    Validate datasets against the GSA DCAT schema.

    :param datasets: A list of datasets to validate.
    :raises SchemaError: If the schema is invalid.
    :return: A list containing invalid datasets.
    """
    invalid_datasets = []
    schemas_folder = Path(__file__).resolve().parent / "schemas"
    schema_path = schemas_folder / "gsa-dcat.json"
    format_checker = FormatChecker()

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    validator = Draft7Validator(schema, format_checker=format_checker)

    for dataset in datasets:
        error_messages = []

        for error in validator.iter_errors(dataset):
            # Create a user-friendly path to the error field
            field_path = " -> ".join(map(str, error.path))

            # Format a more descriptive message
            if field_path:
                error_messages.append(f"{field_path}: {error.message}")
            else:
                # For errors at the very top level of the dataset
                error_messages.append(error.message)

        if error_messages:
            invalid_datasets.append(
                {
                    "title": dataset.get("title", "Unknown Title"),
                    "errors": sorted(error_messages),
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
        with open("invalid_datasets.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
