import Ajv, { ErrorObject } from "npm:ajv@8.17.1";
import addFormats from "npm:ajv-formats@3.0.1";
import schemaFile from "./schemas/dcat-us-1.json" with { type: "json" };

interface ValidationResponse {
  valid: boolean;
  amount: number;
  errors: ValidationError[] | [];
}
interface ValidationError {
  dataPath: string;
  message?: string;
  datasetIdentifier?: string;
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
      const errors = validate.errors.map((err: ErrorObject) => {
        const newErr: ValidationError = {
          dataPath: err.instancePath,
          message: err.message?.replaceAll('"', ""),
        };
        let datasetIdentifier = null;
        if (err.instancePath.includes("/dataset")) {
          datasetIdentifier =
            data.dataset[err.instancePath.split("/")[2]].identifier;
        }
        if (datasetIdentifier) {
          newErr.datasetIdentifier = datasetIdentifier;
        }
        return newErr;
      });

      return {
        valid: false,
        amount: errors.length,
        errors: errors,
      };
    }

    return {
      valid: true,
      amount: 0,
      errors: [],
    };
  } catch (error) {
    throw error;
  }
};
