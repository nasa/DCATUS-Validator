
# DCAT-US JSON Schema Validation Script

This script validates a JSON file against the [DCAT-US Schema](https://resources.data.gov/resources/dcat-us/) (v1.1) and outputs any validation errors in a `validation-results.json` file.

## Usage

Install dependencies:

```bash
npm install
```

Run the script by providing the path to the JSON file you want to validate:

```bash
node dcat-validator.js {input-file-path}
```

Example:

```bash
node dcat-validator.js ./test-json/dcat1-sample.json
```

## Output

- **If the file is valid**: A success message will be logged, and a `validation-results.json` file will be generated containing the following structure.
```json
{
  "isValid": true,
  "amount": 0,
  "errors": []
}
```


- **If the file is invalid**: The script will log the errors, and a `validation-results.json` file will be generated containing the following structure:
```json
{
  "isValid": false,
  "amount": "<number_of_errors>",
  "errors": [
    {
      "datasetTitle": "<name_of_the_dataset>",
      "datasetId": "<dataset_id>",
      "dataPath": "<path_to_the_error>", // This is the path in the input JSON file where the error occurred.
      "keyword": "<error_keyword>",
      "message": "<error_message>",
      "schemaPath": "<path_to_schema_where_error_occurred>", // This is the path in the schema where that flagged the error.
    }
  ]
}
``` 
**Error Notes**:
- If a dataset has multiple errors, each error will be listed separately in the `errors` array.
- If a dataset is breaking multiple rules for a single field(ex: bureauCode), each rule will be listed separately in the `errors` array.
  - Fixing the dataset to adhere to one rule will clear all the errors for that field.

### Notes
- Updated [GSA DCAT-US Schema](https://github.com/GSA/ckanext-datajson/tree/main/ckanext/datajson/pod_schema/federal-v1.1) from draft-04 to draft-07 to keep inline with GSA's schema.
