"""Dataset-level transformations from DCAT-US v3.0 to v1.1.

Each public function takes a dataset dict and returns a transformed copy when a
transformation applies. This is a lossy, best-effort reversal of
`transforms.py`: v3.0's richer structure is collapsed back down to v1.1's
simpler shapes, and fields with no v1.1 equivalent are dropped.

Resources:
- https://resources.data.gov/resources/dcat-us3/
- https://resources.data.gov/resources/dcat-us-3-migration/
"""

import copy
import re

from .transforms import ACCESS_RIGHTS_BY_LEVEL, PERIODICITY_MAP

REVERSE_ACCESS_RIGHTS_BY_LEVEL = {v: k for k, v in ACCESS_RIGHTS_BY_LEVEL.items()}
REVERSE_PERIODICITY_MAP = {v: k for k, v in PERIODICITY_MAP.items()}

# v3.0-only fields with no v1.1 equivalent, dropped by `remove_v3_only_fields()`.
V3_ONLY_FIELDS = {
    "dataset": [
        "otherIdentifier",
        "sample",
        "status",
        "supportedSchema",
        "versionNotes",
        "first",
        "hasCurrentVersion",
        "previousVersion",
        "hasVersion",
        "qualifiedRelation",
        "spatialResolutionInMeters",
        "temporalResolution",
        "liabilityStatement",
        "metadataDistribution",
        "purpose",
        "accessRestriction",
        "cuiRestriction",
        "useRestriction",
        "inventoried",
        "provenance",
        "replaces",
        "hasQualityMeasurement",
        "page",
        "qualifiedAttribution",
        "wasAttributedTo",
        "wasGeneratedBy",
        "wasUsedBy",
        "image",
        "scopeNote",
        "created",
    ],
    "distribution": [
        "representationTechnique",
        "characterEncoding",
        "accessService",
        "compressFormat",
        "packageFormat",
        "availability",
        "inventoried",
        "checksum",
        "otherIdentifier",
    ],
    "catalog": [
        "datasetSeries",
        "record",
        "service",
        "themeTaxonomy",
        "creator",
        "hasPart",
        "otherIdentifier",
        "homepage",
        "qualifiedAttribution",
    ],
}


def remove_v3_only_fields(obj: dict, kind: str) -> dict:
    """Drop fields that exist in v3.0 but have no v1.1 equivalent.

    :param obj: The catalog, dataset, or distribution dict to strip.
    :param kind: One of "catalog", "dataset", or "distribution", selecting
        which field list from :data:`V3_ONLY_FIELDS` to drop.
    :return: A copy of `obj` with the v3.0-only fields removed.
    """
    fields = V3_ONLY_FIELDS.get(kind, [])
    new_obj = copy.deepcopy(obj)
    for field in fields:
        new_obj.pop(field, None)
    return new_obj


def reverse_transform_conforms_to(dataset: dict) -> dict:
    """Convert `conformsTo` from an array of Standard objects back to a
    single URI string, on both the Dataset and each nested Distribution.

    Takes the first array element's `identifier`. Leaves values that are
    already strings, or otherwise not a non-empty list of Standard
    objects, alone.
    """
    new_dataset = copy.deepcopy(dataset)
    _downgrade_conforms_to(new_dataset)
    for distribution in new_dataset.get("distribution", []):
        _downgrade_conforms_to(distribution)
    return new_dataset


def reverse_transform_described_by(dataset: dict) -> dict:
    """Convert `describedBy` from a Distribution object back to a URL
    string, at both the Dataset level and on each nested Distribution.

    Unfolds `mediaType` back out into a separate `describedByType` field.
    Leaves `describedBy` alone where it is absent or already a string.
    """
    new_dataset = copy.deepcopy(dataset)
    _downgrade_described_by(new_dataset)
    for distribution in new_dataset.get("distribution", []):
        _downgrade_described_by(distribution)
    return new_dataset


def reverse_transform_temporal(dataset: dict) -> dict:
    """Convert `temporal` from a list of PeriodOfTime objects back to an
    ISO 8601 interval string ("startDate/endDate").

    Takes the first array element only. Missing `startDate`/`endDate`
    become an empty side of the interval. Returns the dataset unchanged
    if `temporal` is absent, empty, or not a list.
    """
    value = dataset.get("temporal")
    if not isinstance(value, list) or not value:
        return dataset

    period = value[0]
    if not isinstance(period, dict):
        return dataset

    start = period.get("startDate", "")
    end = period.get("endDate", "")
    if not start and not end:
        return dataset

    new_dataset = copy.deepcopy(dataset)
    new_dataset["temporal"] = f"{start}/{end}"
    return new_dataset


def reverse_transform_spatial(dataset: dict) -> dict:
    """Convert `spatial` from a list of Location objects back to a plain
    string.

    Takes the first array element. Parses a WKT `bbox` POLYGON back into
    "<minLon>,<minLat>,<maxLon>,<maxLat>" format; otherwise falls back to
    `prefLabel`. Returns the dataset unchanged if `spatial` is absent,
    empty, or not a list.
    """
    value = dataset.get("spatial")
    if not isinstance(value, list) or not value:
        return dataset

    location = value[0]
    if not isinstance(location, dict):
        return dataset

    new_dataset = copy.deepcopy(dataset)
    bbox_wkt = location.get("bbox")
    if isinstance(bbox_wkt, str):
        bbox = _parse_polygon_wkt(bbox_wkt)
        if bbox is not None:
            new_dataset["spatial"] = ",".join(str(n) for n in bbox)
            return new_dataset

    pref_label = location.get("prefLabel")
    if isinstance(pref_label, str):
        new_dataset["spatial"] = pref_label
        return new_dataset

    del new_dataset["spatial"]
    return new_dataset


def reverse_transform_language(dataset: dict) -> dict:
    """No-op: ISO 639-1 codes are valid RFC 5646 tags as-is.

    Returns the dataset unchanged.
    """
    return dataset


def reverse_transform_access_level(dataset: dict) -> dict:
    """Derive `accessLevel` from `accessRights` when `accessLevel` is
    missing, using the reverse of `ACCESS_RIGHTS_BY_LEVEL`.

    Does not remove `accessRights`. Returns the dataset unchanged if
    `accessLevel` is already present or `accessRights` doesn't match a
    known value.
    """
    if "accessLevel" in dataset:
        return dataset

    access_rights = dataset.get("accessRights")
    if access_rights not in REVERSE_ACCESS_RIGHTS_BY_LEVEL:
        return dataset

    new_dataset = copy.deepcopy(dataset)
    new_dataset["accessLevel"] = REVERSE_ACCESS_RIGHTS_BY_LEVEL[access_rights]
    return new_dataset


def reverse_transform_accrual_periodicity(dataset: dict) -> dict:
    """Convert `accrualPeriodicity` back to an ISO 8601 duration string.

    v1.1 has no separate `accrualPeriodicity`/`modified` split the way
    v3.0 does, so when the dataset lacks a `modified` date, the mapped
    duration is used to populate `modified` instead. Leaves unmapped
    periodicity values (e.g. "irregular") alone. Returns the dataset
    unchanged if `accrualPeriodicity` is absent.
    """
    periodicity = dataset.get("accrualPeriodicity")
    if not isinstance(periodicity, str):
        return dataset

    duration = REVERSE_PERIODICITY_MAP.get(periodicity)
    if duration is None:
        return dataset

    new_dataset = copy.deepcopy(dataset)
    if "modified" not in new_dataset or not new_dataset["modified"]:
        new_dataset["modified"] = duration
    del new_dataset["accrualPeriodicity"]
    return new_dataset


def reverse_transform_rights(dataset: dict) -> dict:
    """Convert `rights` from an array of strings back to a single string.

    Joins multiple entries with "; ". Returns the dataset unchanged if
    `rights` is absent or already a string.
    """
    if "rights" not in dataset:
        return dataset

    value = dataset["rights"]
    if isinstance(value, str):
        return dataset

    new_dataset = copy.deepcopy(dataset)
    if isinstance(value, list) and value:
        new_dataset["rights"] = "; ".join(str(v) for v in value)
    else:
        del new_dataset["rights"]
    return new_dataset


def reverse_transform_sub_organization_of(dataset: dict) -> dict:
    """Unwrap `publisher.subOrganizationOf` (and any nested chain of the
    same field) from arrays back to single Organization objects.

    Takes the first element at each level of the chain. Returns the
    dataset unchanged if there is no publisher or no `subOrganizationOf`
    to unwrap.
    """
    if "publisher" not in dataset:
        return dataset

    publisher = dataset["publisher"]
    if not isinstance(publisher, dict) or "subOrganizationOf" not in publisher:
        return dataset

    new_dataset = copy.deepcopy(dataset)
    _unwrap_sub_organization_of(new_dataset["publisher"])
    return new_dataset


def reverse_transform_landing_page(dataset: dict) -> dict:
    """Convert `landingPage` from a Document object back to a plain URL
    string, extracting `accessURL`.

    Returns the dataset unchanged if `landingPage` is absent or already
    a string.
    """
    if "landingPage" not in dataset:
        return dataset

    value = dataset["landingPage"]
    if not isinstance(value, dict):
        return dataset

    new_dataset = copy.deepcopy(dataset)
    access_url = value.get("accessURL")
    if isinstance(access_url, str):
        new_dataset["landingPage"] = access_url
    else:
        del new_dataset["landingPage"]
    return new_dataset


def reverse_transform_issued_and_modified(dataset: dict) -> dict:
    """Ensure `issued` and `modified` are date or date-time strings, which
    v1.1 allows for both. v3.0-produced values already satisfy this, so
    this is a pass-through validation step: non-string values are left
    alone.
    """
    return dataset


def _downgrade_conforms_to(obj: dict) -> None:
    """Downgrade `conformsTo` on `obj` in place from an array containing
    Standard objects to a single URI string."""
    if "conformsTo" not in obj:
        return
    value = obj["conformsTo"]
    if not isinstance(value, list) or not value:
        return
    first = value[0]
    if isinstance(first, dict) and isinstance(first.get("identifier"), str):
        obj["conformsTo"] = first["identifier"]
    elif isinstance(first, str):
        obj["conformsTo"] = first


def _downgrade_described_by(obj: dict) -> None:
    """Downgrade `describedBy` in place from a Distribution object to a
    URL string, unfolding `mediaType` into a new `describedByType`
    field."""
    if "describedBy" not in obj:
        return
    value = obj["describedBy"]
    if not isinstance(value, dict):
        return
    access_url = value.get("accessURL")
    if not isinstance(access_url, str):
        del obj["describedBy"]
        return
    media_type = value.get("mediaType")
    obj["describedBy"] = access_url
    if isinstance(media_type, str):
        obj["describedByType"] = media_type


def _unwrap_sub_organization_of(organization: dict) -> None:
    """Recursively unwrap `subOrganizationOf` from arrays, in place.

    Assumes `organization` is a v3.0-shaped Organization where
    `subOrganizationOf`, if present, is an array of Organization
    objects. Walks the chain and unwraps each level, taking the first
    element.
    """
    if "subOrganizationOf" not in organization:
        return
    parent = organization["subOrganizationOf"]
    if isinstance(parent, dict):
        # Already unwrapped (recurse in case it still has an array chain).
        _unwrap_sub_organization_of(parent)
        return
    if not isinstance(parent, list) or not parent:
        del organization["subOrganizationOf"]
        return
    first = parent[0]
    if not isinstance(first, dict):
        del organization["subOrganizationOf"]
        return
    _unwrap_sub_organization_of(first)
    organization["subOrganizationOf"] = first


_WKT_POLYGON_RE = re.compile(
    r"^POLYGON\s*\(\(\s*"
    r"([-\d.]+)\s+([-\d.]+)\s*,\s*"
    r"([-\d.]+)\s+([-\d.]+)\s*,\s*"
    r"([-\d.]+)\s+([-\d.]+)\s*,\s*"
    r"([-\d.]+)\s+([-\d.]+)\s*,\s*"
    r"([-\d.]+)\s+([-\d.]+)\s*"
    r"\)\)$",
    re.IGNORECASE,
)


def _parse_polygon_wkt(value: str) -> tuple[float, float, float, float] | None:
    """Parse a closed, axis-aligned rectangular POLYGON WKT string (as
    produced by `transforms._bbox_to_polygon_wkt`) back into
    (minLon, minLat, maxLon, maxLat), or None if it doesn't match."""
    match = _WKT_POLYGON_RE.match(value.strip())
    if not match:
        return None

    coords = [float(n) for n in match.groups()]
    lons = coords[0::2]
    lats = coords[1::2]
    return (min(lons), min(lats), max(lons), max(lats))
