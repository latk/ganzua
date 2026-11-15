import dataclasses
import string
import typing as t

import httpx2
import pydantic
import yarl

from . import _fault_injection as fault_injection

if t.TYPE_CHECKING:
    from ._diff import Diff
    from ._lockfile import LockedPackageNoMeta, Lockfile


class PyPIMetadata(t.TypedDict):
    """Extra PyPI metadata that relates to a specific package version.

    *Added in Ganzua 0.5.0*.
    """

    yanked: t.NotRequired[str]
    """If this package version was yanked, the reason given.

    If no reason was given, a yanked package will use an empty string here.
    """

    vulnerabilities: t.NotRequired[list["Vulnerability"]]
    """If this package version has vulnerabilities, details on those."""

    project_urls: t.NotRequired[t.Mapping["WellKnownProjectUrlLabel | str", str]]
    """The project URLs declared in the package metadata (label → url).

    Well-known labels will have been replaced by their canonical name,
    e.g. `What's New?` will be replaced by `changelog`.

    Specifications:
    * <https://packaging.python.org/en/latest/specifications/core-metadata/#project-url-multiple-use>
    * <https://packaging.python.org/en/latest/specifications/well-known-project-urls/#well-known-project-urls>
    """


class Vulnerability(t.TypedDict, total=False):
    """Information about a known vulnerability for a specific package version.

    Matches the [PyPI JSON API](https://docs.pypi.org/api/json/#known-vulnerabilities) exactly,
    which in turn is based on the [Open Source Vulnerability format](https://ossf.github.io/osv-schema/).
    """

    # PyPI serializes the vulnerability object here:
    # https://github.com/pypi/warehouse/blob/295cdfbc31de8ea0ee04884184021892101daa4a/warehouse/legacy/api/json.py#L131-L148
    # All fields are guaranteed to be present, but the OSV format only requires `id` and `modified` (not present).
    # The corresponding database model is here:
    # https://github.com/pypi/warehouse/blob/c0b58730cbd4a6907ce1c9c6a6af369a9986b8fd/warehouse/integrations/vulnerabilities/models.py#L39-L70
    # We try to stick to the JSON field order here and match the Warehouse database model types,
    # but for OSV-compatibility allow nullable fields to be missing.
    id: t.Required[str]
    source: t.Required[str]
    link: str | None
    aliases: list[str] | None
    details: str | None
    summary: str | None
    fixed_in: list[str] | None
    withdrawn: str | None


WellKnownProjectUrlLabel = t.Literal[
    "homepage",
    "source",
    "download",
    "changelog",
    "releasenotes",
    "documentation",
    "issues",
    "funding",
    "security",
]

WELL_KNOWN_PROJECT_URL_LABELS: t.Mapping[WellKnownProjectUrlLabel, t.Sequence[str]] = {
    "homepage": [],
    "source": ["repository", "sourcecode", "github"],
    "download": [],
    "changelog": ["changes", "whatsnew", "history"],
    "releasenotes": [],
    "documentation": ["docs"],
    "issues": ["bugs", "issue", "tracker", "issuetracker", "bugtracker"],
    "funding": ["sponsor", "donate", "donation"],
    "security": ["securitypolicy"],
}
"""Canonical label names and their aliases.

Source: <https://packaging.python.org/en/latest/specifications/well-known-project-urls/#well-known-labels>
"""


class _ReleaseResponse(t.TypedDict):
    """Schema for a PyPI `GET /pypi/{project}/{version}/json` response.

    Only includes fields that are relevant for Ganzua.

    Docs: <https://docs.pypi.org/api/json/#get-a-release>
    """

    info: "_ReleaseResponseInfo"
    vulnerabilities: list[Vulnerability]


class _ReleaseResponseInfo(t.TypedDict):
    project_urls: t.Mapping[str, str] | None
    yanked: bool
    yanked_reason: str | None


_ReleaseResponseAdapter = pydantic.TypeAdapter(_ReleaseResponse)


@dataclasses.dataclass(kw_only=True)
class PyPIMetadataLoader:
    base_url: yarl.URL
    client: httpx2.Client
    log_error: t.Callable[[httpx2.Response, pydantic.ValidationError | None], None]

    def load(self, *, package: str, version: str) -> PyPIMetadata | None:
        url = self.base_url / f"pypi/{package}/{version}/json"
        res = self.client.get(str(url), headers={"accept": "application/json"})
        if not res.is_success:
            self.log_error(res, None)
            return None

        response_content = res.content
        if fault_injection.current().get("pypi_metadata_invalid_response"):
            response_content = b'{"info": {}, "vulnerabilities": {}}'
        try:
            release = _ReleaseResponseAdapter.validate_json(response_content)
        except pydantic.ValidationError as err:
            self.log_error(res, err)
            return None

        # Translate the response into our data model.
        meta = PyPIMetadata()
        match release:
            case {"info": {"yanked": True, "yanked_reason": yanked}}:
                meta["yanked"] = yanked or ""
        match release:
            case {"vulnerabilities": vulnerabilities} if vulnerabilities:
                meta["vulnerabilities"] = vulnerabilities
        match release:
            case {"info": {"project_urls": project_urls}} if project_urls:
                meta["project_urls"] = {
                    _canonical_project_url_label(label): url
                    for label, url in project_urls.items()
                }
        return meta

    class EnrichmentTarget(t.TypedDict):
        pypi_metadata: t.NotRequired[PyPIMetadata]
        is_yanked: t.NotRequired[bool]
        is_vulnerable: t.NotRequired[bool]

    def enrich(self, target: EnrichmentTarget, package: "LockedPackageNoMeta") -> None:
        # Is the package even eligible for enrichment?
        if package["source"] not in ("default", "pypi"):
            return

        meta = self.load(package=package["name"], version=package["version"])
        if meta is None:
            return

        target["pypi_metadata"] = meta
        if meta.get("yanked") is not None:
            target["is_yanked"] = True
        if (vulns := meta.get("vulnerabilities")) and any(
            not vuln.get("withdrawn") for vuln in vulns
        ):
            target["is_vulnerable"] = True

    def enrich_lockfile(self, target: "Lockfile") -> None:
        for p in target["packages"]:
            self.enrich(target=p, package=p)

    def enrich_diff(self, target: "Diff") -> None:
        for entry in target.packages:
            if entry["new"] is not None:
                self.enrich(target=entry, package=entry["new"])


_CANONICAL_PROJECT_URL_LABEL: t.Mapping[str, WellKnownProjectUrlLabel] = {
    **{
        alias: canonical
        for canonical, aliases in WELL_KNOWN_PROJECT_URL_LABELS.items()
        for alias in aliases
    },
    **{canonical: canonical for canonical in WELL_KNOWN_PROJECT_URL_LABELS},
}

_PROJECT_URL_LABEL_REMOVAL_MAP = str.maketrans(
    "", "", string.punctuation + string.whitespace
)
"""A `str.translate()` map that deletes all ASCII punctuation and whitespace.

Spec: <https://packaging.python.org/en/latest/specifications/well-known-project-urls/#label-normalization>
"""


def _canonical_project_url_label(label: str) -> WellKnownProjectUrlLabel | str:
    """Implements label normalization and then looks up potential canonical names.

    Spec: https://packaging.python.org/en/latest/specifications/well-known-project-urls/#label-normalization

    >>> _canonical_project_url_label("What's New?")
    'changelog'
    >>> _canonical_project_url_label("Some other label!")
    'Some other label!'
    """
    normalized_label = label.translate(_PROJECT_URL_LABEL_REMOVAL_MAP).lower()
    return _CANONICAL_PROJECT_URL_LABEL.get(normalized_label, label)
