import fs from "fs/promises";
import Ajv from "ajv";

const inputFile = process.argv[2];
const outputFile = `validation-results.json`;
const DCAT_US_SCHEMA = JSON.parse(await fs.readFile("./schemas/gsa-dcat.json", "utf8"))

if (!inputFile) {
  console.error("Please provide an input file path.");
  process.exit(1);
}

const validateDcatFile = async (inputFile) => {
  try {
    const fileContent = await fs.readFile(inputFile, "utf8");
    const data = JSON.parse(fileContent);

    const ajv = new Ajv();
    const validate = ajv.compile(DCAT_US_SCHEMA)
    let results = []
    // const valid = validate(data);

    for (let i = 0; i < data.dataset.length; i++) {
      const dataset = data.dataset[i];
      const valid = validate(dataset);
      if (!valid) {
        validate.errors.map((err) => {
          const error = {
            datasetId: dataset.identifier,
            datasetTitle: dataset.title,
            dataPath: `dataset[${i}]${err.dataPath}`,
            keyword: err.keyword,
            message: err.message,
            schemaPath: err.schemaPath,
            // params: err.params,
          }
          results.push(error)
        });
      }
    }

    if(results.length){
      console.log("File failed validation.");
      return {
        isValid: false,
        amount: results.length,
        errors: results
      };
    }

    console.log("Validation succeeded. The file is valid according to the schema.");
    return {
      isValid: true,
      errors: [],
    };
  } 
  catch (error) {
    throw error;
  }
};

try {
  const results = await validateDcatFile(inputFile);
  const outputJSON = JSON.stringify(results, null, 2);
  await fs.writeFile(outputFile, outputJSON);
  console.log(`Validation results written to ${outputFile}`);
} catch (error) {
  console.error(`Error: ${error.message}`);
  process.exit(1);
}
