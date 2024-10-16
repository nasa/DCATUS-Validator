export const validData = {
    "@context": "https://project-open-data.cio.gov/v1.1/schema/catalog.jsonld",
    "@id": "http://example.com/catalog",
    "@type": "dcat:Catalog",
    "conformsTo": "https://project-open-data.cio.gov/v1.1/schema",
    "describedBy": "https://project-open-data.cio.gov/v1.1/schema/catalog.json",
    "dataset": [
      {
        "@type": "dcat:Dataset",
        "identifier": "dataset-001",
        "title": "Example Dataset",
        "description": "This is an example dataset",
        "keyword": ["example", "test"],
        "modified": "2023-04-22",
        "bureauCode": ["026:00"],
        "programCode": ["026:001"],
        "publisher": {
          "@type": "org:Organization",
          "name": "Example Organization"
        },
        "contactPoint": {
          "@type": "vcard:Contact",
          "fn": "John Doe",
          "hasEmail": "mailto:john.doe@example.com"
        },
        "accessLevel": "public",
        "references": ["https://journals.ametsoc.org/doi/10.1175/1520-0493(1997)125<2896:AOTLSA>2.0.CO;2", "https://data.nasa.gov/developer"]
      }
    ]
  };
  
  export const invalidData = {
    "@context": "https://project-open-data.cio.gov/v1.1/schema/catalog.jsonld",
    "@type": "dcat:Catalog",
    "dataset": [
      {
        "@type": "dcat:Dataset",
        "identifier": "dataset-002",
        "title": "Invalid Dataset",
        "description": "This is an invalid dataset",
        "keyword": "not-an-array",
        "modified": "invalid-date",
        "publisher": {
          "name": "Example Organization"
        },
        "contactPoint": {
          "fn": "Jane Doe"
        },
        "accessLevel": "invalid-access-level"
      }
    ]
  };