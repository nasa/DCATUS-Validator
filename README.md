# DCATUS-Validator

A Python tool for validating DCAT-US 1.1 (Data Catalog Vocabulary - United States) JSON files.

## Overview

DCATUS-Validator is a command-line utility developed by NASA to ensure that data catalog files conform to the Project Open Data metadata format required for federal open data initiatives. The tool validates JSON files containing dataset metadata against the official GSA DCAT schema and provides detailed error reporting for non-compliant datasets.


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

## Usage

### Basic Usage

Validate a DCAT-US JSON file:

```bash
python validate.py path/to/your/data.json
```

### Example

```bash
python validate.py test-json/dcat1-sample.json
```

### Output

The validator provides console output showing:
- Number of datasets being validated
- Validation completion status

If validation errors are found:
- An `invalid_datasets.json` file is created with detailed error information
- Each invalid dataset includes:
  - Dataset title
  - List of specific validation errors with field paths

## Test Data

The `test-json/` directory contains sample dataset for testing:

- `dcat1-sample.json` - Basic valid dataset example

## Related Resources

- [DCAT-US Schema Documentation](https://project-open-data.cio.gov/v1.1/schema/)

