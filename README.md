
# DCATUS-Validator

A Python tool for validating and converting DCAT-US JSON catalog files.

## Overview

DCATUS-Validator is a command-line utility developed by NASA to help agencies ensure their data catalog files conform to the DCAT-US metadata format required for federal open data initiatives. It supports both:

- **DCAT-US v1.1**
- **DCAT-US v3.0**

The tool has three scripts:

- `validate.py` - validates the datasets in a catalog against a DCAT-US schema version and reports errors
- `upgrade.py` - upgrades a DCAT-US v1.1 catalog into a DCAT-US v3.0 catalog
- `downgrade.py` - downgrades a DCAT-US v3.0 catalog into a DCAT-US v1.1 catalog (lossy: v3.0-only fields are dropped)

## Requirements

- Python 3.12 or higher
- Dependencies managed via `uv` (see `pyproject.toml`)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/nasa/DCATUS-Validator.git
cd DCATUS-Validator
```

2. Install dependencies using `uv`:
```bash
uv sync
```

## Installing as a package

Instead of cloning the repo, you can add DCATUS-Validator directly as a dependency of your own project from GitHub using `uv`:

```bash
uv add git+https://github.com/nasa/DCATUS-Validator.git
```

Once installed, the package is importable as `dcatus_validator`, and you can call the validate and convert functions directly in your own Python code instead of using the CLI scripts:

```python
from dcatus_validator.validate import validate_catalog, validate_datasets
from dcatus_validator.upgrade import upgrade_dcat_catalog
from dcatus_validator.downgrade import downgrade_dcat_catalog

# Validate an entire catalog and get a list of error strings
errors = validate_catalog(catalog, schema_version="v3.0")

# Validate each dataset individually and get back only the invalid ones
invalid_datasets = validate_datasets(catalog["dataset"], schema_version="v3.0")

# Upgrade a DCAT-US v1.1 catalog dict into a DCAT-US v3.0 catalog dict
new_catalog = upgrade_dcat_catalog(old_catalog)

# Downgrade a DCAT-US v3.0 catalog dict into a DCAT-US v1.1 catalog dict
old_catalog_again = downgrade_dcat_catalog(new_catalog)
```

## Validating a catalog via CLI

Run the `dcatus-validate` command against a DCAT-US catalog JSON file. Each dataset in the file is checked individually against the JSON schemas in `schemas/`.

```bash
uv run dcatus-validate path/to/your/catalog.json
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-s`, `--schema-version` | Schema version to validate against: `v1.1` or `v3.0` | `v3.0` |
| `-o`, `--output` | Path to write the invalid-dataset report | `invalid_datasets.json` |

### Examples

```bash
# Validate a v1.1 catalog
uv run dcatus-validate test_json/dcat1-sample.json -s v1.1

# Validate a v3.0 catalog (default schema version)
uv run dcatus-validate test_json/dcat3-sample.json

# Write the error report to a custom location
uv run dcatus-validate test_json/dcat1-sample.json -s v1.1 -o my_report.json
```

### Output

The script prints the number of datasets checked and how many passed or failed.

- If every dataset is valid, it logs `All datasets are valid.` and exits successfully.
- If any dataset is invalid, it writes a JSON report (default `invalid_datasets.json`) listing each invalid dataset's title and its validation errors, and exits with a non-zero status.

## Upgrading a catalog (v1.1 to v3.0) via CLI

Run the `dcatus-upgrade` command to upgrade a DCAT-US v1.1 catalog into DCAT-US v3.0 format. The script validates the input, upgrades the catalog and its datasets, then validates the result.

```bash
uv run dcatus-upgrade path/to/your/catalog.json
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-o`, `--output-dir` | Directory to write the upgraded catalog to | `converted_dcat_data` |
| `--dry-run` | Upgrade and validate in memory without writing any files | off |
| `--strict` | Exit with an error if the upgraded catalog fails v3.0 validation | off |

### Examples

```bash
# Upgrade a v1.1 catalog and write the result to converted_dcat_data/catalog.json
uv run dcatus-upgrade test_json/dcat1-sample.json

# Preview the upgrade without writing output
uv run dcatus-upgrade test_json/dcat1-sample.json --dry-run

# Upgrade to a custom output directory and fail on invalid v3.0 output
uv run dcatus-upgrade test_json/dcat1-sample.json -o converted_dcat_data --strict
```

### Output

- The upgraded catalog is written to `<output-dir>/catalog.json` (default `converted_dcat_data/catalog.json`), unless `--dry-run` is used.
- If any upgraded datasets fail v3.0 validation, they are also written to `<output-dir>/invalid_datasets.json`.
- Summary counts (datasets processed, valid/invalid before and after upgrade) are printed to the console.

## Downgrading a catalog (v3.0 to v1.1) via CLI

Run the `dcatus-downgrade` command to downgrade a DCAT-US v3.0 catalog into DCAT-US v1.1 format. This is a **lossy** conversion: v3.0 has fields and structure with no v1.1 equivalent, and these are dropped. The script validates the input, downgrades the catalog and its datasets, then validates the result.

```bash
uv run dcatus-downgrade path/to/your/catalog.json
```

### Options

| Option | Description | Default |
| --- | --- | --- |
| `-o`, `--output-dir` | Directory to write the downgraded catalog to | `downgraded_dcat_data` |
| `--dry-run` | Downgrade and validate in memory without writing any files | off |
| `--strict` | Exit with an error if the downgraded catalog fails v1.1 validation | off |

### Examples

```bash
# Downgrade a v3.0 catalog and write the result to downgraded_dcat_data/catalog.json
uv run dcatus-downgrade test_json/dcat3-sample.json

# Preview the downgrade without writing output
uv run dcatus-downgrade test_json/dcat3-sample.json --dry-run

# Downgrade to a custom output directory and fail on invalid v1.1 output
uv run dcatus-downgrade test_json/dcat3-sample.json -o downgraded_dcat_data --strict
```

### Output

- The downgraded catalog is written to `<output-dir>/catalog.json` (default `downgraded_dcat_data/catalog.json`), unless `--dry-run` is used.
- If any downgraded datasets fail v1.1 validation, they are also written to `<output-dir>/invalid_datasets.json`.
- Summary counts (datasets processed, valid/invalid before and after downgrade) are printed to the console.
- Fields that exist only in v3.0 (e.g. `otherIdentifier`, `status`, `provenance`, distribution `checksum`) are dropped during downgrade.

## Schemas

The `schemas/` directory contains the JSON schemas used for validation:

- `schemas/dcat1/` - DCAT-US v1.1 schemas (catalog, dataset)
- `schemas/dcat3/` - DCAT-US v3.0 schemas (catalog, dataset, distribution, organization, and related types)

## Test Data

The `test_json/` directory contains sample catalogs for testing:

- `dcat1-sample.json` - Example DCAT-US v1.1 catalog
- `dcat3-sample.json` - Example DCAT-US v3.0 catalog

## Related Resources

- [DCAT-US v1.1 Schema](https://resources.data.gov/resources/dcat-us/)
- [DCAT-US v3.0 Schema](https://resources.data.gov/resources/dcat-us3/)
- [GSA DCAT-US Repo](https://github.com/GSA/dcat-us)
