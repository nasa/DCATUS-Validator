
# DCAT-US JSON Schema Validation Script

This script validates a JSON file against the [DCAT-US Schema](https://resources.data.gov/resources/dcat-us/) (v1) and outputs any validation errors in a `validation-errors.json` file.

## Usage

Install dependencies:

```bash
npm install
```

Run the script by providing the path to the JSON file you want to validate:

```bash
node validate-dcat.js {input-file-path}
```

Example:

```bash
node validate-dcat.js ./data/dcat-file.json
```

## Output

- **If the file is valid**: A success message will be logged, and no errors will be written.
- **If the file is invalid**: The script will log the errors, and a `validation-errors.json` file will be generated containing the following structure:

```json
{
  "isValid": false,
  "amount": "<number_of_errors>",
  "errors": [
    {
      "dataPath": "<path_to_invalid_data>",
      "message": "<error_message>",
      "datasetIdentifier": "<dataset_identifier_if_applicable>"
    }
  ]
}
``` 

### Notes
- Updated [GSA DCAT-US Schema](https://github.com/GSA/ckanext-datajson/tree/main/ckanext/datajson/pod_schema/federal-v1.1) to draft-07 from draft-04 to keep inline with GSA's schema.
- Did not keep validation for "REDACTED" values.
