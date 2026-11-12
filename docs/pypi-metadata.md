# PyPI metadata

Ganzua can optionally fetch metadata about lockfile entries from PyPI,
which will also warn about yanked or known-vulnerable packages.
Support varies by subcommand:

* [`ganzua inspect`](cli/ganzua-inspect.md) (`--pypi-metadata`)\
  Enrich locked packages with metadata from PyPI.\
  Added in *Ganzua NEXT*.

* [`ganzua diff`](cli/ganzua-diff.md) (`--pypi-metadata`)\
  Enrich `new` packages with metadata from PyPI.\
  Added in *Ganzua NEXT*.

## Security

Using the PyPI metadata feature has security consequences
for how Ganzua works (external network requests!)
and for how you use the Ganzua output.

**External network requests.**
Making external network requests to the PyPI servers should be reasonably safe:

* the PyPI metadata feature is off by default
* Ganzua will only request metadata of packages that look like they are sourced from PyPI
* Ganzua uses well-maintained libraries like [httpx2](https://github.com/pydantic/httpx2)
* Ganzua will only connect to the `pypi.org` servers, using encrypted HTTPS connections, and only using safe HTTP GET operations

However, Ganzua cannot guarantee that your installation is up to date.
It is your responsibility to keep your system up to date,
which may involve re-installing or upgrading Ganzua to upgrade Ganzua's own dependencies
(even if Ganzua did not have a new release).

Ganzua's PyPI metadata feature might not work in exotic network setups,
e.g. when proxies or private certificates are involved.
You may be able to use [`httpx2` environment variables](https://pydantic.dev/docs/httpx2/api/environment_variables/) to configure Ganzua appropriately.

**Using metadata safely.**
When you use the PyPI metadata to make security-relevant decisions,
note that Ganzua only returns whatever is provided by the PyPI API,
which may be inaccurate, out of date, or incomplete.

* Project URLs and yanking depend on package maintainers.
* PyPI sources vulnerabilities from the [PyPA advisory database](https://github.com/pypa/advisory-database), but the snapshot in the PyPI metadata may be out of date.
* Ganzua only supports fetching metadata from PyPI.
  Packages that are installed from third-party registries or from direct URLs are ignored.

Vulnerability details may include arbitrary Markdown, and thus arbitrary HTML.
When using the Ganzua `--pypi-metadata` feature in combination with `--format=markdown`,
strongly consider using a HTML sanitizer before rendering the output.
GitHub should automatically sanitize content in comments and file previews,
so it's always safe to copy&paste Ganzua output into a GitHub comment.

## Example setup

<!-- doctest: clean example -->

To demonstrate PyPI metadata features, we need a lockfile with interesting packages,
e.g. packages with known-problematic versions:

<!-- doctest: create uv lockfile $EXAMPLE/uv.lock -->

| name              | version   |
|-------------------|-----------|
| pluggy            | 1.6.0     |
| typing-extensions | 4.16.0    |
| pydantic-core     | 2.41.3    |
| certifi           | 2026.7.22 |

<details><summary>Also add an empty lockfile</summary>

<!-- doctest: create uv lockfile $EXAMPLE/empty.uv.lock -->

| name | version |
|------|---------|

</details>

## JSON output

We can now inspect these dependencies as JSON.

**No relevant metadata.**
[`pluggy==1.6.0`](https://pypi.org/project/pluggy/1.6.0/) has no relevant metadata.
But the metadata lookup succeeded, so the `pypi_metadata` field is present but empty.

<details><summary><code>$ ganzua inspect --pypi-metadata --filter=pluggy $EXAMPLE</code></summary>

```json
{
  "packages": [
    {
      "name": "pluggy",
      "version": "1.6.0",
      "source": "pypi",
      "pypi_metadata": {}
    }
  ]
}
```

</details>

**Project URLs.**
[`typing-extensions==4.16.0`](https://pypi.org/project/typing-extensions/4.16.0/) has interesting Project URLs.
Whereas some labels are normalized (`Changes` → `changelog`, `Bug Tracker` → `issues`),
the `Q & A` label is not well-known and thus left as-is.

<details><summary><code>$ ganzua inspect --pypi-metadata --filter=typing-extensions $EXAMPLE</code></summary>

```json
{
  "packages": [
    {
      "name": "typing-extensions",
      "version": "4.16.0",
      "source": "pypi",
      "pypi_metadata": {
        "project_urls": {
          "issues": "https://github.com/python/typing_extensions/issues",
          "changelog": "https://github.com/python/typing_extensions/blob/main/CHANGELOG.md",
          "documentation": "https://typing-extensions.readthedocs.io/",
          "Home": "https://github.com/python/typing_extensions",
          "Q & A": "https://github.com/python/typing/discussions",
          "source": "https://github.com/python/typing_extensions"
        }
      }
    }
  ]
}
```

</details>

**Yanked packages.**
[`pydantic-core==2.41.3`](https://pypi.org/project/pydantic_core/2.41.3/) was yanked.
The `pypi_metadata.yanked` field is present and contains a reason,
and the `is_yanked: true` flag is set.

<details><summary><code>$ ganzua inspect --pypi-metadata --filter=pydantic-core $EXAMPLE</code></summary>

```json
{
  "packages": [
    {
      "name": "pydantic-core",
      "version": "2.41.3",
      "source": "pypi",
      "pypi_metadata": {
        "yanked": "corrupted wheel got uploaded",
        "project_urls": {
          "funding": "https://github.com/sponsors/samuelcolvin",
          "homepage": "https://github.com/pydantic/pydantic-core",
          "source": "https://github.com/pydantic/pydantic-core"
        }
      },
      "is_yanked": true
    }
  ]
}
```

</details>

**Vulnerabilities.**
[`certifi==2026.7.22`](https://pypi.org/project/certifi/2026.7.22/) has a known vulnerability.
The `pypi_metadata.vulnerabilities` list is present,
and the `is_vulnerable: true` flag is set.

<details><summary><code>$ ganzua inspect --pypi-metadata --filter=certifi $EXAMPLE</code></summary>

```json
{
  "packages": [
    {
      "name": "certifi",
      "version": "2026.7.22",
      "source": "pypi",
      "pypi_metadata": {
        "vulnerabilities": [
          {
            "id": "GHSA-6q48-6c7w-9gw2",
            "source": "osv",
            "link": "https://osv.dev/vulnerability/GHSA-6q48-6c7w-9gw2",
            "aliases": [
              "PYSEC-2026-4320"
            ],
            "details": "Certifi versions before 2026.10.18 include the `emSign ECC Root CA - G3` root certificate in their bundled CA store. Eight eMudhra intermediate CA certificates that chain to this root have compromised private keys and the CA has revoked them. \n\nAn attacker with one of the compromised keys can issue valid-looking certificates for any hostname. If the attacker is also on-path, they can intercept or modify TLS traffic from clients that trust the certifi bundle. Examples include `requests`, `urllib3` and `pip`, and the Python.org macOS installer.\n\nCertifi 2026.10.18 removed all emSign roots from the bundle. Certifi 2026.10.19 restored the emSign roots that are not affected. Upgrade to 2026.10.19 or later, and rebuild container images that vendor certifi.",
            "summary": null,
            "fixed_in": [
              "2026.10.18"
            ],
            "withdrawn": null
          },
          {
            "id": "PYSEC-2026-4320",
            "source": "osv",
            "link": "https://osv.dev/vulnerability/PYSEC-2026-4320",
            "aliases": [
              "GHSA-6q48-6c7w-9gw2"
            ],
            "details": "Certifi versions before 2026.10.18 include the `emSign ECC Root CA - G3` root certificate in their bundled CA store. Eight eMudhra intermediate CA certificates that chain to this root have compromised private keys and the CA has revoked them. \n\nAn attacker with one of the compromised keys can issue valid-looking certificates for any hostname. If the attacker is also on-path, they can intercept or modify TLS traffic from clients that trust the certifi bundle. Examples include `requests`, `urllib3` and `pip`, and the Python.org macOS installer.\n\nCertifi 2026.10.18 removed all emSign roots from the bundle. Certifi 2026.10.19 restored the emSign roots that are not affected. Upgrade to 2026.10.19 or later, and rebuild container images that vendor certifi.",
            "summary": null,
            "fixed_in": [
              "2026.10.18"
            ],
            "withdrawn": null
          }
        ],
        "project_urls": {
          "homepage": "https://github.com/certifi/python-certifi",
          "source": "https://github.com/certifi/python-certifi"
        }
      },
      "is_vulnerable": true
    }
  ]
}
```

</details>

**Non-PyPI packages.**
The JSON output will only contain a `pypi_metadata` entry
if the package looks like it was installed from PyPI and the metadata lookup succeeded.

To demonstrate this, we can set up a pathological lockfile:

<!-- doctest: create uv lockfile $EXAMPLE/unknown.uv.lock -->

| name           | version | source_toml                              |
|----------------|---------|------------------------------------------|
| local          | 0.0.1   | `{editable = "some/path" }`              |
| other-registry | 1.2.3   | `{registry = "https://example.com"}`     |
| sys            | 3.15    | `{registry = "https://pypi.org/simple"}` |

* The `local` and `other-registry` packages are clearly not installed from PyPI,
  so the metadata lookup will be skipped for them.
* This lockfile declares that a `sys` package was installed from PyPI,
  but no such package exists (PyPI prohibits packages that could be confused with standard library modules).
  Thus, the metadata lookup will be attempted, but it will fail.
  The output will contain a warning message.

<details><summary><code>$ ganzua inspect --pypi-metadata $EXAMPLE/unknown.uv.lock</code></summary>

```
WARNING: PyPI metadata request failed: 404 GET https://pypi.org/pypi/sys/3.15/json
{
  "packages": [
    {
      "name": "local",
      "version": "0.0.1",
      "source": {
        "direct": "some/path"
      }
    },
    {
      "name": "other-registry",
      "version": "1.2.3",
      "source": {
        "registry": "https://example.com"
      }
    },
    {
      "name": "sys",
      "version": "3.15",
      "source": "pypi"
    }
  ]
}
```

</details>

**Error handling.**
If the PyPI response succeeded but the JSON does not match the expected schema,
a warning will be logged, and the `pypi_metadata` key will be absent.
This is tested here via fault injection, not via the live PyPI API.

<!-- doctest: fault injection {"pypi_metadata_invalid_response": true} -->

<details><summary><code>$ ganzua inspect --pypi-metadata --filter=pydantic-core $EXAMPLE</code></summary>

```
WARNING: PyPI metadata request failed: 200 GET https://pypi.org/pypi/pydantic-core/2.41.3/json 4 validation errors for _ReleaseResponse
info.project_urls
  Field required [type=missing, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/latest/v/missing
info.yanked
  Field required [type=missing, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/latest/v/missing
info.yanked_reason
  Field required [type=missing, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/latest/v/missing
vulnerabilities
  Input should be a valid array [type=list_type, input_value={}, input_type=dict]
    For further information visit https://errors.pydantic.dev/latest/v/list_type
{
  "packages": [
    {
      "name": "pydantic-core",
      "version": "2.41.3",
      "source": "pypi"
    }
  ]
}
```

</details>

<!-- doctest: fault injection {} -->

## Markdown output

When we use the Markdown output format,
the table will show (Y) yanked and (V) vulnerable notes.
Note that project URLs are not show in Markdown output.

<details><summary><code>$ ganzua inspect --pypi-metadata --format=markdown $EXAMPLE</code></summary>

```
| package           | version   | notes     |
|-------------------|-----------|-----------|
| certifi           | 2026.7.22 | (V1) (V2) |
| pluggy            | 1.6.0     |           |
| pydantic-core     | 2.41.3    | (Y)       |
| typing-extensions | 4.16.0    |           |

* (V1) [GHSA-6q48-6c7w-9gw2](https://osv.dev/vulnerability/GHSA-6q48-6c7w-9gw2)

  <details><summary>Details</summary>

  Certifi versions before 2026.10.18 include the `emSign ECC Root CA - G3` root certificate in their bundled CA store. Eight eMudhra intermediate CA certificates that chain to this root have compromised private keys and the CA has revoked them. 

  An attacker with one of the compromised keys can issue valid-looking certificates for any hostname. If the attacker is also on-path, they can intercept or modify TLS traffic from clients that trust the certifi bundle. Examples include `requests`, `urllib3` and `pip`, and the Python.org macOS installer.

  Certifi 2026.10.18 removed all emSign roots from the bundle. Certifi 2026.10.19 restored the emSign roots that are not affected. Upgrade to 2026.10.19 or later, and rebuild container images that vendor certifi.

  </details>

  Aliases: PYSEC-2026-4320

  Fixed in: 2026.10.18
* (V2) [PYSEC-2026-4320](https://osv.dev/vulnerability/PYSEC-2026-4320)

  <details><summary>Details</summary>

  Certifi versions before 2026.10.18 include the `emSign ECC Root CA - G3` root certificate in their bundled CA store. Eight eMudhra intermediate CA certificates that chain to this root have compromised private keys and the CA has revoked them. 

  An attacker with one of the compromised keys can issue valid-looking certificates for any hostname. If the attacker is also on-path, they can intercept or modify TLS traffic from clients that trust the certifi bundle. Examples include `requests`, `urllib3` and `pip`, and the Python.org macOS installer.

  Certifi 2026.10.18 removed all emSign roots from the bundle. Certifi 2026.10.19 restored the emSign roots that are not affected. Upgrade to 2026.10.19 or later, and rebuild container images that vendor certifi.

  </details>

  Aliases: GHSA-6q48-6c7w-9gw2

  Fixed in: 2026.10.18
* (Y) yanked: corrupted wheel got uploaded
```

</details>

## Diffs

The PyPI metadata feature can also be used with `ganzua diff`.
Ganzua first calculates the package diff,
and then fetches PyPI metadata for the `new` packages.

For these examples, we compare an empty lockfile with the lockfile used for the `ganzua inspect` examples above,
so we expect essentially equivalent output to an inspect call.

In **JSON output**, the `pypi_metadata` is added to the diff entry object,
including the `is_yanked` and `is_vulnerable` markers.

<details><summary><code>$ ganzua diff --pypi-metadata $EXAMPLE/empty.uv.lock $EXAMPLE</code></summary>

```json
{
  "stat": {
    "total": 4,
    "added": 4,
    "removed": 0,
    "updated": 0
  },
  "packages": [
    {
      "name": "certifi",
      "old": null,
      "new": {
        "name": "certifi",
        "version": "2026.7.22",
        "source": "pypi"
      },
      "pypi_metadata": {
        "vulnerabilities": [
          {
            "id": "GHSA-6q48-6c7w-9gw2",
            "source": "osv",
            "link": "https://osv.dev/vulnerability/GHSA-6q48-6c7w-9gw2",
            "aliases": [
              "PYSEC-2026-4320"
            ],
            "details": "Certifi versions before 2026.10.18 include the `emSign ECC Root CA - G3` root certificate in their bundled CA store. Eight eMudhra intermediate CA certificates that chain to this root have compromised private keys and the CA has revoked them. \n\nAn attacker with one of the compromised keys can issue valid-looking certificates for any hostname. If the attacker is also on-path, they can intercept or modify TLS traffic from clients that trust the certifi bundle. Examples include `requests`, `urllib3` and `pip`, and the Python.org macOS installer.\n\nCertifi 2026.10.18 removed all emSign roots from the bundle. Certifi 2026.10.19 restored the emSign roots that are not affected. Upgrade to 2026.10.19 or later, and rebuild container images that vendor certifi.",
            "summary": null,
            "fixed_in": [
              "2026.10.18"
            ],
            "withdrawn": null
          },
          {
            "id": "PYSEC-2026-4320",
            "source": "osv",
            "link": "https://osv.dev/vulnerability/PYSEC-2026-4320",
            "aliases": [
              "GHSA-6q48-6c7w-9gw2"
            ],
            "details": "Certifi versions before 2026.10.18 include the `emSign ECC Root CA - G3` root certificate in their bundled CA store. Eight eMudhra intermediate CA certificates that chain to this root have compromised private keys and the CA has revoked them. \n\nAn attacker with one of the compromised keys can issue valid-looking certificates for any hostname. If the attacker is also on-path, they can intercept or modify TLS traffic from clients that trust the certifi bundle. Examples include `requests`, `urllib3` and `pip`, and the Python.org macOS installer.\n\nCertifi 2026.10.18 removed all emSign roots from the bundle. Certifi 2026.10.19 restored the emSign roots that are not affected. Upgrade to 2026.10.19 or later, and rebuild container images that vendor certifi.",
            "summary": null,
            "fixed_in": [
              "2026.10.18"
            ],
            "withdrawn": null
          }
        ],
        "project_urls": {
          "homepage": "https://github.com/certifi/python-certifi",
          "source": "https://github.com/certifi/python-certifi"
        }
      },
      "is_vulnerable": true
    },
    {
      "name": "pluggy",
      "old": null,
      "new": {
        "name": "pluggy",
        "version": "1.6.0",
        "source": "pypi"
      },
      "pypi_metadata": {}
    },
    {
      "name": "pydantic-core",
      "old": null,
      "new": {
        "name": "pydantic-core",
        "version": "2.41.3",
        "source": "pypi"
      },
      "pypi_metadata": {
        "yanked": "corrupted wheel got uploaded",
        "project_urls": {
          "funding": "https://github.com/sponsors/samuelcolvin",
          "homepage": "https://github.com/pydantic/pydantic-core",
          "source": "https://github.com/pydantic/pydantic-core"
        }
      },
      "is_yanked": true
    },
    {
      "name": "typing-extensions",
      "old": null,
      "new": {
        "name": "typing-extensions",
        "version": "4.16.0",
        "source": "pypi"
      },
      "pypi_metadata": {
        "project_urls": {
          "issues": "https://github.com/python/typing_extensions/issues",
          "changelog": "https://github.com/python/typing_extensions/blob/main/CHANGELOG.md",
          "documentation": "https://typing-extensions.readthedocs.io/",
          "Home": "https://github.com/python/typing_extensions",
          "Q & A": "https://github.com/python/typing/discussions",
          "source": "https://github.com/python/typing_extensions"
        }
      }
    }
  ]
}
```

</details>

PyPI metadata is only fetched for new packages.
The reverse diff shows that all metadata-related fields are absent.

<details><summary><code>$ ganzua diff --pypi-metadata $EXAMPLE $EXAMPLE/empty.uv.lock</code></summary>

```json
{
  "stat": {
    "total": 4,
    "added": 0,
    "removed": 4,
    "updated": 0
  },
  "packages": [
    {
      "name": "certifi",
      "old": {
        "name": "certifi",
        "version": "2026.7.22",
        "source": "pypi"
      },
      "new": null
    },
    {
      "name": "pluggy",
      "old": {
        "name": "pluggy",
        "version": "1.6.0",
        "source": "pypi"
      },
      "new": null
    },
    {
      "name": "pydantic-core",
      "old": {
        "name": "pydantic-core",
        "version": "2.41.3",
        "source": "pypi"
      },
      "new": null
    },
    {
      "name": "typing-extensions",
      "old": {
        "name": "typing-extensions",
        "version": "4.16.0",
        "source": "pypi"
      },
      "new": null
    }
  ]
}
```

</details>

In **Markdown output**, we get the (Y) yanked and (V) vulnerable notes as in the `ganzua inspect` examples.

<details><summary><code>$ ganzua diff --pypi-metadata --format=markdown $EXAMPLE/empty.uv.lock $EXAMPLE</code></summary>

```
4 changed packages (4 added)

| package           | old | new       | notes     |
|-------------------|-----|-----------|-----------|
| certifi           | -   | 2026.7.22 | (V1) (V2) |
| pluggy            | -   | 1.6.0     |           |
| pydantic-core     | -   | 2.41.3    | (Y)       |
| typing-extensions | -   | 4.16.0    |           |

* (V1) [GHSA-6q48-6c7w-9gw2](https://osv.dev/vulnerability/GHSA-6q48-6c7w-9gw2)

  <details><summary>Details</summary>

  Certifi versions before 2026.10.18 include the `emSign ECC Root CA - G3` root certificate in their bundled CA store. Eight eMudhra intermediate CA certificates that chain to this root have compromised private keys and the CA has revoked them. 

  An attacker with one of the compromised keys can issue valid-looking certificates for any hostname. If the attacker is also on-path, they can intercept or modify TLS traffic from clients that trust the certifi bundle. Examples include `requests`, `urllib3` and `pip`, and the Python.org macOS installer.

  Certifi 2026.10.18 removed all emSign roots from the bundle. Certifi 2026.10.19 restored the emSign roots that are not affected. Upgrade to 2026.10.19 or later, and rebuild container images that vendor certifi.

  </details>

  Aliases: PYSEC-2026-4320

  Fixed in: 2026.10.18
* (V2) [PYSEC-2026-4320](https://osv.dev/vulnerability/PYSEC-2026-4320)

  <details><summary>Details</summary>

  Certifi versions before 2026.10.18 include the `emSign ECC Root CA - G3` root certificate in their bundled CA store. Eight eMudhra intermediate CA certificates that chain to this root have compromised private keys and the CA has revoked them. 

  An attacker with one of the compromised keys can issue valid-looking certificates for any hostname. If the attacker is also on-path, they can intercept or modify TLS traffic from clients that trust the certifi bundle. Examples include `requests`, `urllib3` and `pip`, and the Python.org macOS installer.

  Certifi 2026.10.18 removed all emSign roots from the bundle. Certifi 2026.10.19 restored the emSign roots that are not affected. Upgrade to 2026.10.19 or later, and rebuild container images that vendor certifi.

  </details>

  Aliases: GHSA-6q48-6c7w-9gw2

  Fixed in: 2026.10.18
* (Y) yanked: corrupted wheel got uploaded
```

</details>
