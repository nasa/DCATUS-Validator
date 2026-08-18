"""Validate DCAT-US v1.1 and v3.0 catalogs and datasets.

Home for the schema-registry loading, validation, and error-formatting
helpers shared by the conversion script.
"""

import json
import logging
import sys
from typing import TypedDict

import click
from jsonschema import Draft202012Validator
from referencing import Registry
from utils.errors import format_error
from utils.schemas import SCHEMA_VERSIONS, load_schema_registry


class InvalidDataset(TypedDict):
    """One dataset that failed validation, with its formatted errors."""

    title: str
    errors: list[str]


class CatalogValidationException(Exception):
    """Raised when a catalog fails schema validation and the caller treats it as fatal."""


def _collect_errors(validator: Draft202012Validator, document: dict) -> list[str]:
    """
    Validate a document and return its errors as deduplicated, sorted strings.

    :param validator: A validator from :func:`_build_validator`.
    :param document: The document to validate.
    :return: Formatted error strings; empty when the document is valid.
    """
    return sorted({format_error(error) for error in validator.iter_errors(document)})


def _build_validator(schema_id: str, registry: Registry) -> Draft202012Validator:
    """
    Create a Draft 2020-12 validator that resolves ``schema_id`` through a registry.

    :param schema_id: The ``$id`` of the schema to validate against.
    :param registry: A Registry produced by :func:`load_schema_registry`.
    :return: A configured Draft202012Validator.
    """
    return Draft202012Validator(
        {"$ref": schema_id},
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def validate_catalog(catalog: dict, schema_version: str = "v3.0") -> list[str]:
    """
    Validate a catalog and return formatted error strings instead of raising.

    Callers decide whether a failure is fatal; raise
    :class:`CatalogValidationException` yourself if it is.

    :param catalog: The catalog document to validate.
    :param schema_version: The DCAT-US schema version to validate against.
    :return: Deduplicated, sorted error strings; empty when the catalog is valid.
    """
    version = SCHEMA_VERSIONS[schema_version]
    registry = load_schema_registry(version.definitions_dir)
    schema_id = version.catalog_schema_id
    validator = _build_validator(schema_id, registry)
    return _collect_errors(validator, catalog)


def validate_datasets(
    datasets: list[dict], schema_version: str = "v3.0"
) -> list[InvalidDataset]:
    """
    Validate each dataset individually and report only the invalid ones.

    :param datasets: The datasets to validate.
    :param schema_version: The DCAT-US schema version to validate against.
    :return: An :class:`InvalidDataset` per invalid dataset; empty when all are valid.
    """
    version = SCHEMA_VERSIONS[schema_version]
    registry = load_schema_registry(version.definitions_dir)
    validator = _build_validator(version.dataset_schema_id, registry)
    invalid_datasets: list[InvalidDataset] = []

    for dataset in datasets:
        errors = _collect_errors(validator, dataset)
        if errors:
            invalid_datasets.append(
                {
                    "title": dataset.get("title", "Unknown Title"),
                    "errors": errors,
                }
            )

    return invalid_datasets


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _load_catalog(filepath: str) -> dict:
    """
    Read a JSON catalog from disk, exiting with a message on failure.

    :param filepath: Path to the catalog file.
    :return: The parsed catalog document.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error("Error: The file '%s' was not found.", filepath)
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error("Error: Could not decode JSON from the file '%s'.", filepath)
        sys.exit(1)


def _write_report(invalid_datasets: list[InvalidDataset], output: str) -> None:
    """
    Write the invalid-dataset report as JSON.

    :param invalid_datasets: The datasets that failed validation.
    :param output: Path to write the report to.
    """
    with open(output, "w", encoding="utf-8") as f:
        json.dump(invalid_datasets, f, indent=2, ensure_ascii=False)

    logging.info(
        "Wrote report for %d invalid datasets to %s", len(invalid_datasets), output
    )


@click.command()
@click.argument("filepath", type=click.Path(dir_okay=False))
@click.option(
    "-s",
    "--schema-version",
    type=click.Choice(list(SCHEMA_VERSIONS)),
    default="v3.0",
    show_default=True,
    help="DCAT-US schema version to validate against.",
)
@click.option(
    "-o",
    "--output",
    default="invalid_datasets.json",
    show_default=True,
    help="Path to write the invalid-dataset report.",
)
def main(filepath: str, schema_version: str, output: str) -> None:
    """Validate the datasets in a DCAT-US JSON catalog file."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    catalog = _load_catalog(filepath)
    datasets = catalog.get("dataset", []) if isinstance(catalog, dict) else []

    invalid_catalog = validate_catalog(catalog, schema_version)

    logging.info("Validating catalog against DCAT-US %s...", schema_version)
    if invalid_catalog:
        logging.error("Catalog validation failed with %d errors:", len(invalid_catalog))
        for error in invalid_catalog:
            logging.error("  - %s", error)
        sys.exit(1)
    else:
        logging.info("Catalog is valid.")

    logging.info(
        "Validating %d datasets against DCAT-US %s...", len(datasets), schema_version
    )
    invalid_datasets = validate_datasets(datasets, schema_version)
    logging.info("Validation complete.")

    valid_count = len(datasets) - len(invalid_datasets)
    logging.info("%d valid, %d invalid.", valid_count, len(invalid_datasets))

    if not invalid_datasets:
        logging.info("All datasets are valid.")
        return

    _write_report(invalid_datasets, output)
    sys.exit(1)


if __name__ == "__main__":
    main()
