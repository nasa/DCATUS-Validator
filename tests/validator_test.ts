import { assertEquals, assertNotEquals, assertRejects } from "jsr:@std/assert";
import { validateFile } from "../schema-validator.ts";
import { invalidData, validData } from "./data.ts";

// Helper function to create temporary test files
async function createTempFile(content: object): Promise<string> {
  const tempFilePath = await Deno.makeTempFile({ suffix: ".json" });
  await Deno.writeTextFile(tempFilePath, JSON.stringify(content));
  return tempFilePath;
}

Deno.test("validateFile with valid input", async () => {
  const tempFilePath = await createTempFile(validData);
  try {
    const result = await validateFile(tempFilePath);
    assertEquals(result.valid, true);
    assertEquals(result.amount, 0);
    assertEquals(result.errors, []);
  } finally {
    await Deno.remove(tempFilePath);
  }
});

Deno.test("validateFile with invalid input", async () => {
  const tempFilePath = await createTempFile(invalidData);
  try {
    const result = await validateFile(tempFilePath);
    assertEquals(result.valid, false);
    assertNotEquals(result.amount, 0);
    assertNotEquals(result.errors.length, 0);

    // Check for specific errors
    // const errorMessages = result.errors.map(error => error.message);
    // assertEquals(errorMessages.some(msg => msg.includes("must be array")), true);
    // assertEquals(errorMessages.some(msg => msg.includes("must match format \"date-time\"")), true);
    // assertEquals(errorMessages.some(msg => msg.includes("must be equal to one of the allowed values")), true);
  } finally {
    await Deno.remove(tempFilePath);
  }
});

Deno.test("validateFile with invalid DOI URI", async () => {
  const tempData = {
    ...validData,
    dataset: [
      {
        ...validData.dataset[0],
        references: [
          "badURI",
          "https://data.nasa.gov/developer",
          "https://example.com/\x19test",
        ],
      },
    ],
  };
  const tempFilePath = await createTempFile(tempData);
  try {
    const result = await validateFile(tempFilePath);

    assertEquals(result.valid, false);
    assertNotEquals(result.amount, 0);
    assertNotEquals(result.errors.length, 0);
  } finally {
    await Deno.remove(tempFilePath);
  }
});

Deno.test("validateFile with invalid JSON", async () => {
  const tempFilePath = await Deno.makeTempFile({ suffix: ".json" });
  await Deno.writeTextFile(tempFilePath, "This is not valid JSON");
  try {
    await assertRejects(
      () => validateFile(tempFilePath),
      Error,
    );
  } finally {
    await Deno.remove(tempFilePath);
  }
});

Deno.test("validateFile with non-existent file", async () => {
  await assertRejects(
    () => validateFile("non_existent_file.json"),
    Error,
  );
});
