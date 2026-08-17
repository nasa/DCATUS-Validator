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


def validate_catalog(schema_id: str, registry: Registry, catalog: dict) -> list[str]:
    """
    Validate a catalog and return formatted error strings instead of raising.

    Callers decide whether a failure is fatal; raise
    :class:`CatalogValidationException` yourself if it is.

    :param schema_id: The catalog schema ``$id`` to validate against.
    :param registry: A Registry produced by :func:`load_schema_registry`.
    :param catalog: The catalog document to validate.
    :return: Deduplicated, sorted error strings; empty when the catalog is valid.
    """
    return _collect_errors(_build_validator(schema_id, registry), catalog)


def validate_datasets(
    schema_id: str, registry: Registry, datasets: list[dict]
) -> list[InvalidDataset]:
    """
    Validate each dataset individually and report only the invalid ones.

    :param schema_id: The dataset schema ``$id`` to validate against.
    :param registry: A Registry produced by :func:`load_schema_registry`.
    :param datasets: The datasets to validate.
    :return: An :class:`InvalidDataset` per invalid dataset; empty when all are valid.
    """
    validator = _build_validator(schema_id, registry)
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
    version = SCHEMA_VERSIONS[schema_version]
    catalog = _load_catalog(filepath)
    datasets = catalog.get("dataset", []) if isinstance(catalog, dict) else []

    registry = load_schema_registry(version.definitions_dir)

    logging.info(
        "Validating %d datasets against DCAT-US %s...", len(datasets), schema_version
    )
    invalid_datasets = validate_datasets(version.dataset_schema_id, registry, datasets)
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
