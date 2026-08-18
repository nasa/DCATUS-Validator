import json
from dataclasses import dataclass
from pathlib import Path

from referencing import Registry, Resource


@dataclass(frozen=True)
class SchemaVersion:
    catalog_schema_id: str
    dataset_schema_id: str
    definitions_dir: Path


SCRIPT_DIR = Path(__file__).resolve().parent.parent

SCHEMA_VERSIONS: dict[str, SchemaVersion] = {
    "v1.1": SchemaVersion(
        catalog_schema_id="https://project-open-data.cio.gov/v1.1/schema/catalog.json",
        dataset_schema_id="https://project-open-data.cio.gov/v1.1/schema/dataset.json",
        definitions_dir=SCRIPT_DIR / "schemas" / "dcat1",
    ),
    "v3.0": SchemaVersion(
        catalog_schema_id="https://resources.data.gov/dcat-us/3.0.0/definitions/catalog",
        dataset_schema_id="https://resources.data.gov/dcat-us/3.0.0/definitions/dataset",
        definitions_dir=SCRIPT_DIR / "schemas" / "dcat3",
    ),
}


def _reference_aliases(schema_file: Path, contents: dict) -> list[str]:
    """
    Every URI a sibling schema might use to reference this one.

    Aliases come from the filename on disk, not the ``$id``, so multi-word
    names survive intact (``data-service`` stays ``data-service.json``).
    """
    filename = schema_file.name
    aliases = [filename, f"./{filename}", schema_file.resolve().as_uri()]

    schema_id = contents.get("$id", "")
    if schema_id:
        base = schema_id.rstrip("/#").rpartition("/")[0]
        if base:
            aliases.append(f"{base}/{filename}")

    return aliases


def load_schema_registry(definitions_dir: Path) -> Registry:
    """
    Build a referencing Registry from every JSON schema file in a directory.

    Each schema is registered under its own ``$id`` plus filename-based aliases
    so relative ``$ref`` values and absolute sibling references both resolve.

    :param definitions_dir: Directory containing the schema ``*.json`` files.
    :raises FileNotFoundError: If the directory does not exist.
    :return: A Registry containing all schemas and their aliases.
    """
    if not definitions_dir.is_dir():
        raise FileNotFoundError(
            f"Schema definitions directory not found: {definitions_dir}"
        )

    registry: Registry = Registry()

    for schema_file in sorted(definitions_dir.glob("*.json")):
        contents = json.loads(schema_file.read_text(encoding="utf-8"))
        resource = Resource.from_contents(contents)

        uris = _reference_aliases(schema_file, contents)
        declared_id = resource.id()
        if declared_id:
            uris.append(declared_id)

        registry = registry.with_resources((uri, resource) for uri in uris)

    return registry
