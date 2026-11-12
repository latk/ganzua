import json
import typing as t

import pytest
import tomlkit
import vcr  # type: ignore[import-untyped]

type AnyDict = dict[str, object]


@pytest.fixture(scope="session")
def vcr_config() -> AnyDict:
    """Shared VCR configuration.

    Docs: https://github.com/kiwicom/pytest-recording#configuration
    """
    return {
        "decode_compressed_response": True,
        "allow_playback_repeats": True,
        "before_record_response": lambda response: _vcr_response_pretty_print_json(
            _vcr_response_remove_irrelevant_headers(response),
            transform_body=_vcr_response_redact_json_body,
        ),
        "serializer": "toml",
    }


def pytest_recording_configure(vcr: vcr.VCR) -> None:
    """Register a TOML format for VCR cassettes."""
    vcr.register_serializer("toml", _TomlSerializer())
    vcr.serializer = "toml"


def _vcr_response_remove_irrelevant_headers(response: AnyDict) -> AnyDict:
    """Remove irrelevant headers.

    Docs: https://vcrpy.readthedocs.io/en/latest/advanced.html#custom-response-filtering
    """

    def is_relevant(key: str) -> bool:
        match key:
            # The `False` cases are marked via `pragma: no cover`
            # because they are only exercised when saving new network interactions.
            case (
                "accept-ranges"
                | "connection"
                | "content-security-policy"
                | "permissions-policy"
                | "referred-policy"
                | "server"
                | "strict-transport-security"
            ):  # pragma: no cover
                return False
            case _ if key.startswith(("access-control-", "x-")):  # pragma: no cover
                return False
            case _:
                return True

    if isinstance(headers := response.get("headers"), dict):
        response["headers"] = {
            key: value for key, value in headers.items() if is_relevant(key)
        }
    else:  # pragma: no cover
        pass

    return response


def _vcr_response_pretty_print_json(
    response: AnyDict, transform_body: t.Callable[[AnyDict], AnyDict]
) -> AnyDict:
    """Pretty-print JSON content in the response."""
    match response:
        case {
            "body": {"string": bytes() as body},
            "headers": dict() as headers,
        } if headers.get("content-type") == ["application/json"]:
            data = transform_body(json.loads(body))
            body = json.dumps(data, indent=2).encode("utf-8")
            response["body"] = {"string": body}
            headers["content-length"] = [str(len(body))]
        case _:  # pragma: no cover
            pass

    return response


def _vcr_response_redact_json_body(data: AnyDict) -> AnyDict:
    # Ignore certain response content that's irrelevant for Ganzua.
    if data.get("urls"):
        data["urls"] = ["... ignored ..."]
    else:  # pragma: no cover  # in practice, all packages have URLs
        pass

    if data.get("ownership"):  # pragma: no cover  # only used when redacting fresh data
        data["ownership"] = {}

    # Redact potential PII.
    if isinstance(info := data.get("info"), dict):
        for key in ("author", "author_email", "maintainer", "maintainer_email"):
            if info.get(key):
                info[key] = "REDACTED"
    else:  # pragma: no cover
        pass
    return data


class _TomlSerializer:
    r"""Serialize VCR Cassettes as TOML, using multi-line strings if appropriate.

    >>> s = _TomlSerializer()
    >>> data = {"some": "multiline\ndata", "nested": [{"ints": 1234, "strings": "abc"}]}
    >>> s.deserialize(s.serialize(data)) == data
    True
    """

    def deserialize(self, cassette_string: str) -> AnyDict:
        return tomlkit.loads(cassette_string).unwrap()

    def serialize(self, cassette_dict: AnyDict) -> str:
        return tomlkit.dumps(
            t.cast(dict, self._filter_multiline_strings(cassette_dict))
        )

    def _filter_multiline_strings(self, data: object) -> object:
        # Replace strings with multiline strings if appropriate
        if isinstance(data, str):
            if "\n" in data:
                return tomlkit.string(data, multiline=True, literal=True)
            return data

        # Recurse into containers
        if isinstance(data, t.Sequence):
            return [self._filter_multiline_strings(value) for value in data]
        if isinstance(data, t.Mapping):
            return {
                key: self._filter_multiline_strings(value)
                for key, value in data.items()
            }
        return data
