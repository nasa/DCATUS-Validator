import fs from "fs/promises";
import Ajv from "ajv";
import addFormats from "ajv-formats";

const inputFile = process.argv[2];
const outputFile = `validation-errors.json`;
const DCAT_US_SCHEMA = JSON.parse(await fs.readFile("./schemas/dcat-us-1.json", "utf8"))

if (!inputFile) {
  console.error("Please provide an input file path.");
  process.exit(1);
}

const validateDcatFile = async (inputFile) => {
  try {
    const fileContent = await fs.readFile(inputFile, "utf8");
    const data = JSON.parse(fileContent);
    const ajv = new Ajv({ allErrors: true });

    addFormats(ajv);
    ajv.addFormat("doi-uri", {
      type: "string",
      validate: (str) => {
        try {
          const schemeRegex = /^(https?):\/\//i;
          const decoded = decodeURIComponent(str);

          if (!schemeRegex.test(str)) {
            return false;
          }

          encodeURI(decoded);
          return true;
        } catch (_e) {
          return false;
        }
      },
    });
    
    const validate = ajv.compile(DCAT_US_SCHEMA)
    const valid = validate(data);

    if(!valid){
      console.log("File failed validation.");
      const errors = validate.errors.map((err) => {
        const newErr = {
          dataPath: err.instancePath,
          message: err.message.replaceAll("\"", ""),
        }
        let datasetIdentifier = null;
        if (err.instancePath.includes("/dataset")){
          datasetIdentifier = data.dataset[err.instancePath.split("/")[2]].identifier;
        }
        if (datasetIdentifier) {
          newErr.datasetIdentifier = datasetIdentifier
        }
        return newErr;
      });
      return {
        isValid: false,
        amount: errors.length,
        errors: errors
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
