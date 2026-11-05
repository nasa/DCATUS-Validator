"""Dataset-level transformations from DCAT-US v1.1 to v3.0.

Each public function takes a dataset dict and returns a transformed copy when a
transformation applies.

Resources:
- https://resources.data.gov/resources/dcat-us3/
- https://resources.data.gov/resources/dcat-us-3-migration/
"""

import copy
import re
from datetime import datetime, timezone

import click
from dateutil import parser
from jsonschema import Draft202012Validator
from langcodes import Language, find, tag_is_valid

ACCESS_RIGHTS_BY_LEVEL = {
    "public": "public",
    "restricted public": "Access restricted. Contact the publisher to request access.",
    "non-public": "Not available for public release. Contact the publisher for more information.",
}

# There are four valid-but-unmapped values for `accrualPeriodicity`:
# asNeeded
# irregular
# notPlanned
# unknown
PERIODICITY_MAP = {
    "P1D": "daily",
    "P1W": "weekly",
    "P2W": "fortnightly",
    "P1M": "monthly",
    "P3M": "quarterly",
    "P6M": "biannually",
    "P1Y": "annually",
    "PT1S": "continual",
}


def _is_iri(value: str) -> bool:
    """Report whether `value` satisfies the `iri` format used by v3.0 schemas.

    Delegates to the same format checker the validator runs, so this cannot
    disagree with validation. v1.1 permits non-URL strings wherever a URL is
    expected — notably REDACTED markers like "[[REDACTED-EX B6]]" — and v3.0
    fields declaring `"format": "iri"` reject them.
    """
    checker = Draft202012Validator.FORMAT_CHECKER
    try:
        return checker.check(value, "iri") is None
    except Exception:
        return False


def propagate_license(dataset: dict) -> dict:
    """Copy dataset-level `license` down to each Distribution
    that does not already declare one.

    Does not remove the dataset-level `license`. Returns the dataset
    unchanged if there is no license on the dataset or no distributions
    to copy it to.
    """
    license_value = dataset.get("license")
    if not license_value:
        return dataset

    distributions = dataset.get("distribution")
    if not distributions:
        return dataset

    new_dataset = copy.deepcopy(dataset)
    for dist in new_dataset["distribution"]:
        if isinstance(dist, dict) and "license" not in dist:
            dist["license"] = license_value

    return new_dataset


def transform_access_rights(dataset: dict) -> dict:
    """Add `accessRights` alongside `accessLevel` for DCAT-US 3.0.

    Does not remove `accessLevel`. Per the migration guide's Step 5:
    "Until updated OMB guidance is issued, keep `accessLevel` in your
    records — the v3.0 schema will not reject it."

    Returns the dataset unchanged if `accessLevel` is missing or
    `accessRights` is already set.
    """

    if "accessRights" in dataset:
        return dataset

    access_level = dataset.get("accessLevel")
    if access_level not in ACCESS_RIGHTS_BY_LEVEL:
        return dataset

    new_dataset = copy.deepcopy(dataset)
    new_dataset["accessRights"] = ACCESS_RIGHTS_BY_LEVEL[access_level]
    return new_dataset


def transform_conforms_to(dataset: dict) -> dict:
    """Convert `conformsTo` from a URI string to an array containing a
    Standard object, on both the Dataset and each nested Distribution.

    Per the DCAT-US v3.0 migration guide's "Additional improvements"
    section. Leaves values that are already arrays alone, and leaves
    objects (non-list, non-string) alone.
    """
    new_dataset = copy.deepcopy(dataset)
    _upgrade_conforms_to(new_dataset)
    for distribution in new_dataset.get("distribution", []):
        _upgrade_conforms_to(distribution)
    return new_dataset


def transform_described_by(dataset: dict) -> dict:
    """Convert `describedBy` from a URL string to a Distribution object,
    at both the Dataset level and on each nested Distribution.

    Folds `describedByType` (v1.1) into the new Distribution's `mediaType`.
    Per the DCAT-US v3.0 migration guide's "Additional improvements"
    section. Leaves `describedBy` alone where it is absent or already an
    object.
    """
    new_dataset = copy.deepcopy(dataset)
    _upgrade_described_by(new_dataset)
    for distribution in new_dataset.get("distribution", []):
        _upgrade_described_by(distribution)
    return new_dataset


def transform_issued(dataset: dict) -> dict:
    """DCAT-US v3.0 requires that `issued` be either 'date-time'
    or 'date'."""
    if "issued" not in dataset:
        return dataset

    value = dataset["issued"]

    # Pass through null and non-string values untouched; the schema
    # permits null, and anything non-str isn't ours to reinterpret.
    if not isinstance(value, str):
        return dataset

    new_dataset = copy.deepcopy(dataset)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        # Not a valid ISO date/date-time (e.g. "2019") => unset it.
        del new_dataset["issued"]
        return new_dataset

    if parsed.time() == datetime.min.time():
        # Midnight => no meaningful time component, emit a plain 'date'.
        new_dataset["issued"] = parsed.date().isoformat()  # e.g. 2015-06-02
    else:
        # Normalize to UTC and format as a valid ISO 8601 date-time string (e.g. 2018-09-28T06:00:00Z).
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        new_dataset["issued"] = parsed.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    return new_dataset


def transform_landing_page(dataset: dict) -> dict:
    """Convert `landingPage` from a URL string to a Document object
    with `title` and `accessURL`.

    The title is reused from the dataset's `title` field. Returns the
    dataset unchanged if `landingPage` is absent or not a string.
    """
    if "landingPage" not in dataset:
        return dataset

    value = dataset["landingPage"]
    if not isinstance(value, str):
        return dataset

    new_dataset = copy.deepcopy(dataset)
    document = {"@type": "Document", "accessURL": value}
    if "title" in new_dataset:
        document["title"] = new_dataset["title"]
    new_dataset["landingPage"] = document
    return new_dataset


def transform_language(dataset: dict) -> dict:
    """Truncate RFC 5646 language tags to ISO 639-1 on the dataset and
    any nested distributions. Non-list or non-string entries are left
    alone."""
    new_dataset = copy.deepcopy(dataset)
    _truncate_language(new_dataset)
    for distribution in new_dataset.get("distribution", []):
        _truncate_language(distribution)
    return new_dataset


def transform_modified(dataset: dict) -> dict:
    modified = dataset.get("modified")
    if not isinstance(modified, str):
        return dataset

    if _is_date(modified):
        new_dataset = copy.deepcopy(dataset)
        new_dataset["modified"] = _to_valid_date(modified)
        return new_dataset

    new_dataset = copy.deepcopy(dataset)
    duration = _as_duration(modified)
    mapped_duration = PERIODICITY_MAP.get(duration)
    if mapped_duration is None:
        new_dataset["accrualPeriodicity"] = "irregular"
    else:
        new_dataset["accrualPeriodicity"] = mapped_duration
    # `modified` is Recommended + nullable in DCAT-US v3.0
    del new_dataset["modified"]
    return new_dataset


def transform_references(dataset: dict) -> dict:
    """Convert `references` from an array of URLs to `page`, a list of
    Document objects.

    v1.1's `references` ("Related Documents") and v3.0's `page`
    ("List of pages or documents about this dataset", `foaf:page`,
    range `foaf:Document`) describe the same relation: documentation
    about the dataset that is not the data dictionary. Note that this is
    *not* `isReferencedBy`, which is `dcterms:isReferencedBy` — the
    inverse relation, for resources that cite the dataset.

    The migration guide does not cover `references`, so this mapping is
    inferred from the two schemas' own definitions. See ADR-0004.

    `Document` requires `title`, so the URL is used as the title as well
    as the `accessURL`. Entries that are not valid IRIs get a title but no
    `accessURL`, since that field declares `"format": "iri"` and would fail
    validation. This covers v1.1's REDACTED markers, which are not URLs, as
    well as any malformed entry. Returns the dataset unchanged if
    `references` is absent.
    """
    if "references" not in dataset:
        return dataset

    value = dataset["references"]

    new_dataset = copy.deepcopy(dataset)
    del new_dataset["references"]

    if value is None:
        return new_dataset

    # The v1.1 schema permits a bare REDACTED string in place of the array.
    entries = [value] if isinstance(value, str) else value
    if not isinstance(entries, list):
        return new_dataset

    documents = []
    for entry in entries:
        if not isinstance(entry, str):
            continue
        if _is_iri(entry):
            documents.append({"@type": "Document", "title": entry, "accessURL": entry})
        else:
            documents.append({"@type": "Document", "title": entry})

    if not documents:
        return new_dataset

    existing = new_dataset.get("page")
    if isinstance(existing, list):
        existing.extend(documents)
    else:
        new_dataset["page"] = documents

    return new_dataset


def transform_primary_it_investment_uii(dataset: dict) -> dict:
    """Move `primaryITInvestmentUII` into v3.0's `otherIdentifier` list.

    The migration guide says the v1.1 field "can be preserved in
    `otherIdentifier` if needed"; GSA's reference converter does not do so.
    `Identifier`'s top-level `anyOf` accepts a bare string, so the UII maps
    across with no object construction and no invented data. See ADR-0007.

    Appends to an existing `otherIdentifier` rather than replacing it,
    matching `transform_references()`. Returns the dataset unchanged if
    `primaryITInvestmentUII` is absent.
    """
    if "primaryITInvestmentUII" not in dataset:
        return dataset

    value = dataset["primaryITInvestmentUII"]

    new_dataset = copy.deepcopy(dataset)
    del new_dataset["primaryITInvestmentUII"]

    if not isinstance(value, str) or not value.strip():
        return new_dataset

    existing = new_dataset.get("otherIdentifier")
    if isinstance(existing, list):
        existing.append(value)
    else:
        new_dataset["otherIdentifier"] = [value]

    return new_dataset


def build_dataset_series(
    original_datasets: list, transformed_datasets: list
) -> tuple[list, list]:
    """Promote `isPartOf` parents to catalog-level `datasetSeries` entries.

    Migration guide Step 13, and the only catalog-level transform here: a
    parent moves out of `dataset[]` with its children nested beneath it, so
    this needs every dataset at once and cannot run in the per-dataset loop.

    Linkage resolves against `original_datasets` — the pre-transform
    identifiers — while output is built from `transformed_datasets`,
    matching GSA's converter. The two lists are positional. See ADR-0006.

    :param original_datasets: Datasets as they appeared in the v1.1 input.
    :param transformed_datasets: The same datasets after the per-dataset
        transform chain, in the same order.
    :return: `(dataset_series, top_level_datasets)`. Promoted parents and
        their children are absent from `top_level_datasets`.
    :raises ValueError: On a self-referencing `isPartOf` or a nested series
        (a dataset that is both a parent and a child). `upgrade.py` wraps
        this in `CatalogUpgradeException`.
    """
    # First occurrence wins on duplicate identifiers, matching GSA.
    by_identifier: dict[str, int] = {}
    for i, dataset in enumerate(original_datasets):
        identifier = _series_key(dataset.get("identifier"))
        if identifier and identifier not in by_identifier:
            by_identifier[identifier] = i

    parent_of: dict[int, int] = {}
    orphans: list[tuple[int, str]] = []
    for i, dataset in enumerate(original_datasets):
        is_part_of = _series_key(dataset.get("isPartOf"))
        if not is_part_of:
            continue

        parent_index = by_identifier.get(is_part_of)
        if parent_index is None:
            orphans.append((i, is_part_of))
            continue
        if parent_index == i:
            raise ValueError(
                f"Dataset {is_part_of} declares itself its own isPartOf parent"
            )
        parent_of[i] = parent_index

    children_of: dict[int, list[int]] = {}
    for child_index, parent_index in parent_of.items():
        children_of.setdefault(parent_index, []).append(child_index)

    # `seriesMember` has range `dcat:Dataset`, so it cannot hold a series.
    for parent_index in children_of:
        if parent_index in parent_of:
            identifier = _series_key(original_datasets[parent_index].get("identifier"))
            raise ValueError(
                f"Dataset {identifier} is both a series parent and a series "
                f"member; nested dataset series are not supported"
            )

    for child_index, missing_parent in orphans:
        identifier = _series_key(original_datasets[child_index].get("identifier"))
        click.echo(
            f"Warning: dataset {identifier or f'index {child_index}'} declares "
            f"isPartOf {missing_parent}, which is not in this catalog. Leaving "
            f"it as a top-level dataset with isPartOf intact."
        )

    dataset_series = []
    for parent_index in sorted(children_of):
        series = _build_one_series(
            original_datasets[parent_index],
            transformed_datasets[parent_index],
            [transformed_datasets[c] for c in sorted(children_of[parent_index])],
        )
        dataset_series.append(series)

    promoted = set(children_of) | set(parent_of)
    top_level_datasets = [
        dataset for i, dataset in enumerate(transformed_datasets) if i not in promoted
    ]

    return dataset_series, top_level_datasets


def _build_one_series(
    original_parent: dict, transformed_parent: dict, transformed_children: list
) -> dict:
    """Build one `DatasetSeries` from a promoted parent and its children.

    `@id` declares `"format": "iri"`, which is enforced, and half of NASA's
    identifiers are bare DOIs. A non-IRI identifier therefore stays in
    `identifier` rather than becoming an invalid `@id`; the downgrade reads
    whichever of the two is present. See ADR-0006.
    """
    series = copy.deepcopy(transformed_parent)
    series["@type"] = "DatasetSeries"

    series.pop("first", None)
    series.pop("last", None)
    series.pop("isPartOf", None)

    # `contactPoint` is a single object on a Dataset but a list on a series.
    contact_point = series.get("contactPoint")
    if isinstance(contact_point, dict):
        series["contactPoint"] = [contact_point]

    identifier = _series_key(original_parent.get("identifier"))
    if identifier and _is_iri(identifier):
        series["@id"] = identifier
        series.pop("identifier", None)

    series["seriesMember"] = [copy.deepcopy(child) for child in transformed_children]
    for member in series["seriesMember"]:
        if isinstance(member, dict):
            member.pop("isPartOf", None)

    return series


def _series_key(value) -> str:
    """Return `value` as a stripped string for series linkage, or "" if it
    is not a usable identifier."""
    if not isinstance(value, str):
        return ""
    return value.strip()


def transform_rights(dataset: dict) -> dict:
    """Convert `rights` from a single string to an array of strings.

    Per the DCAT-US v3.0 migration guide's "Additional improvements"
    section. Returns the dataset unchanged if `rights` is absent or
    already a list. Unsets `rights` if it is not a string or list.
    """
    if "rights" not in dataset:
        return dataset

    value = dataset["rights"]
    if isinstance(value, list):
        return dataset

    new_dataset = copy.deepcopy(dataset)
    if isinstance(value, str):
        new_dataset["rights"] = [value]
    else:
        del new_dataset["rights"]
    return new_dataset


def transform_spatial(dataset: dict) -> dict:
    """Convert `spatial` from a plain string or bbox string to a
    list of Location objects.

    Detects bbox format ("<minLon>,<minLat>,<maxLon>,<maxLat>") and emits
    a POLYGON WKT; otherwise treats the value as a prefLabel. Returns the
    dataset unchanged if `spatial` is absent.
    """
    if "spatial" not in dataset:
        return dataset

    value = dataset["spatial"]
    if not isinstance(value, str):
        return dataset

    new_dataset = copy.deepcopy(dataset)
    bbox = _parse_bbox(value)
    if bbox is not None:
        new_dataset["spatial"] = [
            {
                "@type": "Location",
                "bbox": _bbox_to_polygon_wkt(bbox),
            }
        ]
    else:
        new_dataset["spatial"] = [
            {
                "@type": "Location",
                "prefLabel": value,
            }
        ]
    return new_dataset


def transform_sub_organization_of(dataset: dict) -> dict:
    """Wrap `publisher.subOrganizationOf` (and any nested chain of the
    same field) in arrays.

    In v1.1, `subOrganizationOf` is a single Organization object that
    can nest recursively. In v3.0, it must be an array of Organization
    objects (or null). Walks the chain and wraps each level.

    Returns the dataset unchanged if there is no publisher or no
    `subOrganizationOf` to wrap. Leaves values that are already arrays
    alone.
    """
    if "publisher" not in dataset:
        return dataset

    publisher = dataset["publisher"]
    if not isinstance(publisher, dict) or "subOrganizationOf" not in publisher:
        return dataset

    new_dataset = copy.deepcopy(dataset)
    _wrap_sub_organization_of(new_dataset["publisher"])
    return new_dataset


def transform_temporal(dataset: dict) -> dict:
    """Convert `temporal` from an ISO 8601 interval string to a list
    containing one PeriodOfTime. Whichever side(s) parse as a date
    become startDate/endDate; non-date sides (durations or anything
    else) are dropped. No-op if `temporal` isn't a string with one '/'
    or if neither side parses."""
    value = dataset.get("temporal")
    if not isinstance(value, str):
        return dataset

    # Strip repeating interval prefix (e.g. "R/" or "R5/")
    if re.match(r"^R\d*/", value):
        value = re.sub(r"^R\d*/", "", value)

    if value.count("/") != 1:
        return dataset

    left, right = value.split("/")
    start = _as_date(left)
    end = _as_date(right)
    if start is None and end is None:
        return dataset

    period = {"@type": "PeriodOfTime"}
    if start is not None:
        period["startDate"] = start
    if end is not None:
        period["endDate"] = end

    new_dataset = copy.deepcopy(dataset)
    new_dataset["temporal"] = [period]
    return new_dataset


def _as_date(token: str) -> str | None:
    """Return the date portion of `token` if it (a) is a year, (b) is a year and month,
    or (c) parses as an ISO 8601 date or datetime, else None."""
    if len(token) == 4 and token.isdigit():
        return token

    if (
        len(token) == 7
        and token[4] == "-"
        and token[:4].isdigit()
        and token[5:].isdigit()
    ):
        return token

    try:
        return datetime.fromisoformat(token).date().isoformat()
    except ValueError:
        return None


def _as_duration(value: str) -> str | None:
    """Return the bare ISO 8601 duration portion of `value` if it looks
    like a duration or a repeating interval (`R/<duration>` or
    `R<n>/<duration>`), else None."""
    if value.startswith("P"):
        return value
    if value.startswith("R"):
        _, _, rest = value.partition("/")
        if rest.startswith("P"):
            return rest
    return None


def _to_valid_date(value: str) -> str:
    """Return `value` unchanged if it's a Zulu date-time (ends with 'Z').
    Otherwise, truncate to the YYYY-MM-DD portion if possible."""
    if not isinstance(value, str):
        return value

    if value.endswith("Z"):
        return value

    # Datetime-ish string (e.g. "2022-01-01T00:00:00" or "2022-01-01 00:00:00") — take the date part.
    if ("T" in value or " " in value) and len(value) >= 10:
        return value[:10]

    return value


def _upgrade_described_by(obj: dict) -> None:
    """Upgrade `describedBy` in place from a URL string to a Distribution
    object, consuming `describedByType` (removed from `obj`, folded into
    the new Distribution's `mediaType`)."""
    if "describedBy" not in obj:
        return
    value = obj["describedBy"]
    if not isinstance(value, str):
        return
    distribution = {"accessURL": value}
    if "describedByType" in obj:
        distribution["mediaType"] = obj.pop("describedByType")
    obj["describedBy"] = distribution


def _upgrade_conforms_to(obj: dict) -> None:
    """Upgrade `conformsTo` on `obj` in place from a URI string to an
    array containing a Standard object."""
    if "conformsTo" not in obj:
        return
    value = obj["conformsTo"]
    if isinstance(value, list):
        return
    if not isinstance(value, str):
        return
    obj["conformsTo"] = [{"@type": "Standard", "identifier": value}]


def _wrap_sub_organization_of(organization: dict) -> None:
    """Recursively wrap `subOrganizationOf` in arrays, in place.

    Assumes `organization` is a v1.1-shaped Organization where
    `subOrganizationOf`, if present, is a single Organization object.
    Walks the chain and wraps each level.
    """
    if "subOrganizationOf" not in organization:
        return
    parent = organization["subOrganizationOf"]
    if isinstance(parent, list):
        # Already an array (recurse into each element in case any
        # element still has an unwrapped subOrganizationOf).
        for element in parent:
            if isinstance(element, dict):
                _wrap_sub_organization_of(element)
        return
    if not isinstance(parent, dict):
        return
    _wrap_sub_organization_of(parent)
    organization["subOrganizationOf"] = [parent]


def _parse_bbox(value: str) -> tuple[float, float, float, float] | None:
    """Return (minLon, minLat, maxLon, maxLat) if `value` is a comma-
    separated bbox string, otherwise None.

    Note that a more complete implementation of this function is
    available here: https://github.com/GSA/datagov-harvester/blob/main/harvester/utils/general_utils.py#L885-L955
    """
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        return None
    try:
        nums = tuple(float(p) for p in parts)
    except ValueError:
        return None
    return nums  # type: ignore[return-value]


def _bbox_to_polygon_wkt(bbox: tuple[float, float, float, float]) -> str:
    """Convert (minLon, minLat, maxLon, maxLat) to a closed POLYGON WKT
    string. The ring is traversed counter-clockwise and closes by
    repeating the first vertex."""
    min_lon, min_lat, max_lon, max_lat = bbox
    return (
        f"POLYGON(({min_lon} {min_lat}, "
        f"{max_lon} {min_lat}, "
        f"{max_lon} {max_lat}, "
        f"{min_lon} {max_lat}, "
        f"{min_lon} {min_lat}))"
    )


def _truncate_language(obj: dict) -> None:
    tags = obj.get("language")
    if not isinstance(tags, list):
        return

    normalized = []
    for tag in tags:
        if not isinstance(tag, str):
            continue
        try:
            lang = Language.get(tag) if tag_is_valid(tag) else find(tag)
        except LookupError:
            continue
        code = lang.language
        if code:
            normalized.append(code)

    obj["language"] = normalized


def _is_date(string):
    try:
        parser.parse(string)
        return True
    except (ValueError, OverflowError):
        return False
