
# JSON Schema Validation Script

This script validates a file against a specified JSON schema and outputs any validation errors in a `validation-errors.json` file.

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
  "amount": "<number_of_errors>",
  "errors": [
    {
      "dataPath": "<path_to_invalid_data>",
      "message": "<error_message>",
      "context": "<additional_context_if_applicable>"
    }
  ]
}
```

### Notes

- This script is compatible with your schema and provides detailed error messages for easy debugging.
- Be sure to update any schema-specific configurations in `schema-validator.ts` as needed.
