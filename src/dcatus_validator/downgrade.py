"""Downgrade a valid DCAT-US v3.0 catalog to a valid DCAT-US v1.1 catalog.

This is a lossy transformation: v3.0 has richer structure and additional
fields with no v1.1 equivalent. Fields that can't be represented in v1.1
are dropped, with warnings logged so callers know what was lost.
"""

import copy
import json
import sys
from pathlib import Path

import click

from .utils import reverse_transforms as rt
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


class CatalogDowngradeException(Exception):
    pass


def _load_dcat_catalog(filepath: Path) -> dict:
    """Read a DCAT-US v3.0 catalog from disk."""
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


def downgrade_dcat_catalog(v3_catalog: dict) -> dict:
    """Downgrade a DCAT-US v3.0 catalog to a DCAT-US v1.1 catalog."""
    v1_catalog = copy.deepcopy(v3_catalog)

    # Add v1.1 catalog-level fields.
    v1_catalog["@context"] = (
        "https://project-open-data.cio.gov/v1.1/schema/catalog.jsonld"
    )
    v1_catalog["conformsTo"] = "https://project-open-data.cio.gov/v1.1/schema"
    v1_catalog["describedBy"] = (
        "https://project-open-data.cio.gov/v1.1/schema/catalog.json"
    )

    # Remove v3.0-only catalog fields.
    v1_catalog = rt.remove_v3_only_fields(v1_catalog, "catalog")

    datasets = v1_catalog.get("dataset", [])
    click.echo(f"Transforming {len(datasets)} datasets.")
    for i, dataset in enumerate(datasets):
        identifier = dataset.get("identifier", f"index {i}")
        try:
            dataset = rt.reverse_transform_conforms_to(dataset)
            dataset = rt.reverse_transform_described_by(dataset)
            dataset = rt.reverse_transform_temporal(dataset)
            dataset = rt.reverse_transform_spatial(dataset)
            dataset = rt.reverse_transform_language(dataset)
            dataset = rt.reverse_transform_access_level(dataset)
            dataset = rt.reverse_transform_accrual_periodicity(dataset)
            dataset = rt.reverse_transform_rights(dataset)
            dataset = rt.reverse_transform_sub_organization_of(dataset)
            dataset = rt.reverse_transform_landing_page(dataset)
            dataset = rt.reverse_transform_issued_and_modified(dataset)

            distributions = dataset.get("distribution", [])
            for j, distribution in enumerate(distributions):
                distributions[j] = rt.remove_v3_only_fields(
                    distribution, "distribution"
                )

            dataset = rt.remove_v3_only_fields(dataset, "dataset")
            datasets[i] = dataset
        except Exception as e:
            raise CatalogDowngradeException(
                f"Failed to downgrade dataset {identifier}: {e}"
            ) from e

    return v1_catalog


def _export_downgraded_catalog(catalog: dict, output_dir: str) -> None:
    """Write the downgraded DCAT-US v1.1 catalog to disk as JSON."""
    click.echo("Saving downgraded DCAT-US 1.1 to disk.")

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
    "-o", "--output-dir", help="Output directory", default="downgraded_dcat_data"
)
@click.option(
    "--dry-run",
    help="Validate and downgrade DCAT-US v3.0 catalog without saving to disk",
    is_flag=True,
    default=False,
)
@click.option(
    "--strict",
    help="Treat v1.1 catalog validation failure as a fatal error",
    is_flag=True,
    default=False,
)
def main(filepath, output_dir, dry_run, strict):
    """Downgrade a DCAT-US v3.0 catalog file to DCAT-US v1.1."""
    v1_1_registry = load_schema_registry(V1_1.definitions_dir)
    v3_0_registry = load_schema_registry(V3_0.definitions_dir)

    results = {"error": False, "downgrade_successful": False}
    counts = {
        "datasets": 0,
        "valid_v3_0": 0,
        "invalid_v3_0": 0,
        "validation_errors_v3_0": 0,
        "valid_v1_1": 0,
        "invalid_v1_1": 0,
        "validation_errors_v1_1": 0,
    }

    click.echo(f"Downgrading DCAT-US v3.0 to DCAT-US v1.1 for {filepath}")
    try:
        catalog_to_convert = _load_dcat_catalog(filepath)
        datasets = catalog_to_convert.get("dataset", [])
        counts["datasets"] = len(datasets)

        # Catalog-level v3.0 validation (non-fatal)
        v3_0_catalog_errors = validate_catalog(catalog_to_convert, "v3.0")
        if v3_0_catalog_errors:
            click.echo(
                f"Warning: input catalog failed v3.0 validation with "
                f"{len(v3_0_catalog_errors)} error(s) — downgrading anyway."
            )
            for line in v3_0_catalog_errors:
                click.echo(f"  {line}")
        else:
            click.echo("Input catalog is valid DCAT-US v3.0.")

        # Per-dataset v3.0 validation
        invalid_v3_0 = validate_datasets(datasets, "v3.0")
        counts["invalid_v3_0"] = len(invalid_v3_0)
        counts["valid_v3_0"] = len(datasets) - len(invalid_v3_0)
        counts["validation_errors_v3_0"] = _count_errors(invalid_v3_0)
        click.echo(
            f"Per-dataset v3.0: {counts['valid_v3_0']} valid, "
            f"{counts['invalid_v3_0']} invalid."
        )

        downgraded_catalog = downgrade_dcat_catalog(catalog_to_convert)

        # Catalog-level v1.1 validation
        v1_1_catalog_errors = validate_catalog(downgraded_catalog, "v1.1")
        if v1_1_catalog_errors:
            message = (
                f"v1.1 catalog validation failed with "
                f"{len(v1_1_catalog_errors)} error(s)"
            )
            if strict:
                raise CatalogValidationException(message)
            click.echo(f"Invalid DCAT-US data: {message}", err=True)

        # Per-dataset v1.1 validation
        downgraded_datasets = downgraded_catalog.get("dataset", [])
        invalid_v1_1 = validate_datasets(downgraded_datasets, "v1.1")
        counts["invalid_v1_1"] = len(invalid_v1_1)
        counts["valid_v1_1"] = len(downgraded_datasets) - len(invalid_v1_1)
        counts["validation_errors_v1_1"] = _count_errors(invalid_v1_1)
        click.echo(
            f"Per-dataset v1.1: {counts['valid_v1_1']} valid, "
            f"{counts['invalid_v1_1']} invalid."
        )

        if dry_run:
            click.echo("Dry run complete.")
        else:
            _export_downgraded_catalog(downgraded_catalog, output_dir)
            if invalid_v1_1:
                _export_invalid_report(
                    invalid_v1_1, Path(output_dir) / "invalid_datasets.json"
                )

    except CatalogLoadException as e:
        results["error"] = True
        click.echo(
            f"There was an error loading the DCAT-US v3.0 catalog: {e}", err=True
        )

    except CatalogDowngradeException as e:
        results["error"] = True
        click.echo(
            f"There was an error downgrading a DCAT-US v3.0 catalog to DCAT-US v1.1: {e}",
            err=True,
        )
    except CatalogValidationException as e:
        results["error"] = True
        click.echo(f"Downgraded catalog is not valid DCAT-US v1.1: {e}", err=True)

    if not results["error"] and counts["datasets"] == counts["valid_v1_1"]:
        results["downgrade_successful"] = True

    click.echo(f"RESULTS:{json.dumps(results)}")
    click.echo(f"COUNTS:{json.dumps(counts)}")

    if results["error"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
