import { validateFile } from "./schema-validator.ts";

let inputFile: string | null = Deno.args[0];
const outputFile = `validation-errors.json`;

if (!inputFile) {
  inputFile = prompt("Please provide an input file path: ");
  if (!inputFile) {
    console.error("No input file path provided. Exiting...");
    Deno.exit(1);
  }
}

try {
  const results = await validateFile(inputFile);
  results.valid
    ? console.log(
      "Validation succeeded. The file is valid according to the schema.",
    )
    : console.log(
      "Validation failed. The file is not valid according to the schema.",
    );
  const outputJSON = JSON.stringify(results, null, 2);
  await Deno.writeTextFile(outputFile, outputJSON);
  console.log(`Validation results written to ${outputFile}`);
} catch (error: unknown) {
  if (error instanceof Error) {
    throw new Error(`Validation error: ${error.message}`);
  } else {
    throw new Error("An unknown error occurred during validation");
  }
}
