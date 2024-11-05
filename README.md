
# JSON Schema Validation Script

This script validates a file against a specified JSON schema(Default DCAT-US 1.1) and outputs any validation errors in a `validation-errors.json` file.

## Usage

```bash
deno -RW main.ts
```

Run the script by providing the path to the file you want to validate:

```bash
deno -RW main.ts {input-file-path}
```

### Example

```bash
deno -RW main.ts .\test-json\data.json
```

## Output

- **If the file is valid**: A success message will be logged, and no errors will be written.
- **If the file is invalid**: The script will log the errors, and a `validation-errors.json` file will be generated containing the following structure:

```json
{
  "isValid": false,
  "datasetsWithErrors": "<number_of_datasets_with_errors>",
  "errors": [
    {
      "datasetIdentifier": "<dataset_identifier>",
      "amount": "<number_of_errors_in_dataset>",
      "errors": [
        {
          "dataPath": "<path_to_field_with_error>",
          "description": "<description_of_field_with_error>",
          "message": "<error_messages>"
        }
      ]
    }
  ]
}
```

### Notes
- Updated [GSA DCAT-US Schema](https://github.com/GSA/ckanext-datajson/tree/main/ckanext/datajson/pod_schema/federal-v1.1) from draft-04 to draft-07 to keep inline with GSA's schema.
- Did not keep validation for "REDACTED" values.
- This script can be used to validate any JSON file against any JSON schema.