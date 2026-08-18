"""Convert a valid DCAT-US v1.1 catalog to a valid DCAT-US v3.0 catalog."""

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from .utils import transforms
from .utils.schemas import SCHEMA_VERSIONS, load_schema_registry
from .validate import (
    CatalogValidationException,
    InvalidDataset,
    validate_catalog,
    validate_datasets,
)

V1_1 = SCHEMA_VERSIONS["v1.1"]
V3_0 = SCHEMA_VERSIONS["v3.0"]


class CatalogLoadException(Exception):
    pass


class CatalogConversionException(Exception):
    pass


def _load_dcat_catalog(filepath: Path) -> dict:
    """Read a DCAT-US v1.1 catalog from disk."""
    try:
        raw = filepath.read_bytes()
    except OSError as e:
        raise CatalogLoadException(f"Could not read {filepath}: {e}") from e

    # Handle UTF-8 with or without a BOM, falling back to cp1252 for
    # Windows-encoded exports.
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("cp1252")
        except UnicodeDecodeError as e:
            raise CatalogLoadException(f"Could not decode {filepath}: {e}") from e

    try:
        parsed = json.loads(text)
    except ValueError as e:
        raise CatalogLoadException(f"{filepath} was not valid JSON: {e}") from e

    if not isinstance(parsed, dict):
        raise CatalogLoadException(
            f"Expected a JSON object at the catalog root, got {type(parsed).__name__}"
        )

    return parsed


def convert_dcat_catalog(old_catalog: dict) -> dict:
    """Convert DCAT-US v1.1 catalog to DCAT-US v3.0 catalog."""
    new_catalog = copy.deepcopy(old_catalog)

    # conformsTo on the Catalog
    new_catalog["conformsTo"] = {
        "@type": "Standard",
        "title": "DCAT-US 3.0",
        "identifier": "https://resources.data.gov/dcat-us/3.0.0",
    }

    # remove @context and describedBy from the Catalog
    new_catalog.pop("@context", None)
    new_catalog.pop("describedBy", None)

    # The catalog itself may have a `modified` timestamp so we normalize it to a
    # timezone-aware date-time string, since v3.0 requires one.
    catalog_modified = new_catalog.get("modified")
    if isinstance(catalog_modified, str):
        try:
            parsed = datetime.fromisoformat(catalog_modified)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            new_catalog["modified"] = parsed.astimezone(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        except ValueError:
            del new_catalog["modified"]

    datasets = new_catalog.get("dataset", [])
    click.echo(f"Transforming {len(datasets)} datasets.")
    for i, dataset in enumerate(datasets):
        identifier = dataset.get("identifier", f"index {i}")
        try:
            dataset = transforms.transform_modified(dataset)
            dataset = transforms.transform_temporal(dataset)
            dataset = transforms.transform_spatial(dataset)
            dataset = transforms.transform_language(dataset)
            dataset = transforms.transform_access_rights(dataset)
            dataset = transforms.propagate_license(dataset)
            dataset = transforms.transform_rights(dataset)
            dataset = transforms.transform_described_by(dataset)
            dataset = transforms.transform_sub_organization_of(dataset)
            dataset = transforms.transform_conforms_to(dataset)
            dataset = transforms.transform_landing_page(dataset)
            dataset = transforms.transform_issued(dataset)
            datasets[i] = dataset
        except Exception as e:
            raise CatalogConversionException(
                f"Failed to convert dataset {identifier}: {e}"
            ) from e

    return new_catalog


def _export_converted_catalog(catalog: dict, output_dir: str) -> None:
    """Write the converted DCAT-US v3.0 catalog to disk as JSON."""
    click.echo("Saving converted DCAT-US 3.0 to disk.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / "catalog.json"
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    click.echo(f"Wrote {output_file}")


def _export_invalid_report(invalid_datasets: list[InvalidDataset], path: Path) -> None:
    """Write the invalid-dataset report produced by validate_datasets()."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(invalid_datasets, f, indent=2, ensure_ascii=False)
    click.echo(f"Wrote report for {len(invalid_datasets)} invalid datasets to {path}")


def _count_errors(invalid_datasets: list[InvalidDataset]) -> int:
    return sum(len(entry["errors"]) for entry in invalid_datasets)


@click.command()
@click.argument(
    "filepath",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
)
@click.option(
    "-o", "--output-dir", help="Output directory", default="converted_dcat_data"
)
@click.option(
    "--dry-run",
    help="Validate and convert DCAT-US v1.1 catalog without saving to disk",
    is_flag=True,
    default=False,
)
@click.option(
    "--strict",
    help="Treat v3.0 catalog validation failure as a fatal error",
    is_flag=True,
    default=False,
)
def main(filepath, output_dir, dry_run, strict):
    """Convert a DCAT-US v1.1 catalog file to DCAT-US v3.0."""
    v1_1_registry = load_schema_registry(V1_1.definitions_dir)
    v3_0_registry = load_schema_registry(V3_0.definitions_dir)

    results = {"error": False, "conversion_successful": False}
    counts = {
        "datasets": 0,
        "valid_v1_1": 0,
        "invalid_v1_1": 0,
        "validation_errors_v1_1": 0,
        "valid_v3_0": 0,
        "invalid_v3_0": 0,
        "validation_errors_v3_0": 0,
    }

    click.echo(f"Converting DCAT-US v1.1 to DCAT-US v3.0 for {filepath}")
    try:
        catalog_to_convert = _load_dcat_catalog(filepath)
        datasets = catalog_to_convert.get("dataset", [])
        counts["datasets"] = len(datasets)

        # Catalog-level v1.1 validation (non-fatal)
        v1_1_catalog_errors = validate_catalog(catalog_to_convert, "v1.1")
        if v1_1_catalog_errors:
            click.echo(
                f"Warning: input catalog failed v1.1 validation with "
                f"{len(v1_1_catalog_errors)} error(s) — converting anyway."
            )
            for line in v1_1_catalog_errors:
                click.echo(f"  {line}")
        else:
            click.echo("Input catalog is valid DCAT-US v1.1.")

        # Per-dataset v1.1 validation
        invalid_v1_1 = validate_datasets(datasets, "v1.1")
        counts["invalid_v1_1"] = len(invalid_v1_1)
        counts["valid_v1_1"] = len(datasets) - len(invalid_v1_1)
        counts["validation_errors_v1_1"] = _count_errors(invalid_v1_1)
        click.echo(
            f"Per-dataset v1.1: {counts['valid_v1_1']} valid, "
            f"{counts['invalid_v1_1']} invalid."
        )

        converted_catalog = convert_dcat_catalog(catalog_to_convert)

        # Catalog-level v3.0 validation
        v3_0_catalog_errors = validate_catalog(converted_catalog, "v3.0")
        if v3_0_catalog_errors:
            message = (
                f"v3.0 catalog validation failed with "
                f"{len(v3_0_catalog_errors)} error(s):\n"
                + "\n".join(f"  {line}" for line in v3_0_catalog_errors)
            )
            if strict:
                raise CatalogValidationException(message)
            click.echo(f"Invalid DCAT-US data: {message}", err=True)

        # Per-dataset v3.0 validation
        converted_datasets = converted_catalog.get("dataset", [])
        invalid_v3_0 = validate_datasets(converted_datasets, "v3.0")
        counts["invalid_v3_0"] = len(invalid_v3_0)
        counts["valid_v3_0"] = len(converted_datasets) - len(invalid_v3_0)
        counts["validation_errors_v3_0"] = _count_errors(invalid_v3_0)
        click.echo(
            f"Per-dataset v3.0: {counts['valid_v3_0']} valid, "
            f"{counts['invalid_v3_0']} invalid."
        )

        if dry_run:
            click.echo("Dry run complete.")
        else:
            _export_converted_catalog(converted_catalog, output_dir)
            if invalid_v3_0:
                _export_invalid_report(
                    invalid_v3_0, Path(output_dir) / "invalid_datasets.json"
                )

    except CatalogLoadException as e:
        results["error"] = True
        click.echo(
            f"There was an error loading the DCAT-US v1.1 catalog: {e}", err=True
        )

    except CatalogConversionException as e:
        results["error"] = True
        click.echo(
            f"There was an error converting a DCAT-US v1.1 catalog to DCAT-US v3.0: {e}",
            err=True,
        )
    except CatalogValidationException as e:
        results["error"] = True
        click.echo(f"Converted catalog is not valid DCAT-US v3.0: {e}", err=True)

    if not results["error"] and counts["datasets"] == counts["valid_v3_0"]:
        results["conversion_successful"] = True

    click.echo(f"RESULTS:{json.dumps(results)}")
    click.echo(f"COUNTS:{json.dumps(counts)}")

    if results["error"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
