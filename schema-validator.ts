import Ajv, { ErrorObject } from "npm:ajv@8.17.1";
import addFormats from "npm:ajv-formats@3.0.1";
import schemaFile from "./schemas/dcat-us-1.json" with { type: "json" };

interface ValidationResponse {
  valid: boolean;
  datasetsWithErrors: number;
  errors: DatasetErrors[] | [];
}
interface ValidationError {
  dataPath: string;
  message?: string[];
  datasetIdentifier?: string;
}
interface DatasetErrors {
  datasetIdentifier: string;
  errors: {
    dataPath: string;
    message: string;
  }[];
  amount: number;
}

export const validateFile = async (
  inputFile: string,
): Promise<ValidationResponse> => {
  try {
    const data = JSON.parse(await Deno.readTextFile(inputFile));
    // @ts-ignore: Suppressing "This expression is not constructable" error
    const ajv = new Ajv({ allErrors: true });

    // @ts-ignore: Suppressing "This expression is not callable" error
    addFormats(ajv);
    ajv.addFormat("doi-uri", {
      type: "string",
      validate: (str: string): boolean => {
        try {
          const schemeRegex = /^(https?):\/\//i;
          if (!schemeRegex.test(str)) {
            return false;
          }

          const decoded = decodeURIComponent(str);
          encodeURI(decoded);

          return true;
        } catch (_e) {
          return false;
        }
      },
    });

    const validate = ajv.compile(schemaFile);
    const valid = validate(data);

    if (!valid) {
      // Group errors by datasetIdentifier and then by dataPath
      const errorGroups: Record<string, ValidationError[]> = {};

      validate.errors.forEach((err: ErrorObject) => {
        const dataPath = err.instancePath;
        const message = err.message?.replaceAll('"', "");

        let datasetIdentifier = null;
        if (dataPath.includes("/dataset")) {
          datasetIdentifier = data.dataset[dataPath.split("/")[2]].identifier;
        }

        if (datasetIdentifier) {
          if (!errorGroups[datasetIdentifier]) {
            errorGroups[datasetIdentifier] = [];
          }

          // Check if a similar error already exists for deduplication
          const existingError = errorGroups[datasetIdentifier].find(
            (e) => e.dataPath === dataPath
          );

          if (existingError) {
            // Add the message if it's not already in the list
            if (message && existingError.message && !existingError.message.includes(message)) {
              existingError.message.push(message);
            }
          } else {
            // Add a new error entry
            errorGroups[datasetIdentifier].push({
              dataPath,
              message: message ? [message] : [],
              datasetIdentifier,
            });
          }
        }
      });

      // Convert grouped errors into an array of arrays for human-readable output
      const errors: DatasetErrors[] = Object.entries(errorGroups).map(([identifier, errors]) => ({
        datasetIdentifier: identifier,
        amount: errors.length,
        errors: errors.map((err) => ({
          dataPath: err.dataPath,
          message: err.message ? err.message.join("; ") : "",
        })),
      }));

      return {
        valid: false,
        datasetsWithErrors: errors.length,
        errors,
      };
    }

    return {
      valid: true,
      datasetsWithErrors: 0,
      errors: [],
    };
  } catch (error) {
    throw error;
  }
};
