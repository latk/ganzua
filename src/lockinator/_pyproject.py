import tomlkit
import tomlkit.items
from packaging.requirements import Requirement
from tomlkit.container import Container as _TomlContainer
from tomlkit.exceptions import NonExistentKey

from ._constraints import update_requirement
from ._lockfile import Lockfile


def update_pyproject(doc: tomlkit.TOMLDocument, lockfile: Lockfile) -> None:
    # TODO skip path dependencies?
    # TODO support Poetry-specific fields
    # TODO check if there are uv-specific fields
    project = _toml_get_table(doc, "project")

    _update_requirements_array(_toml_get_array(project, "dependencies"), lockfile)

    optional_dependencies = _toml_get_table(project, "optional-dependencies")
    for extra in optional_dependencies:
        _update_requirements_array(
            _toml_get_array(optional_dependencies, extra), lockfile
        )

    dependency_groups = _toml_get_table(doc, "dependency-groups")
    for group in dependency_groups:
        _update_requirements_array(_toml_get_array(dependency_groups, group), lockfile)


def _update_requirements_array(reqs: tomlkit.items.Array, lockfile: Lockfile) -> None:
    for i, old in enumerate(list(reqs)):
        if not isinstance(old, str):
            continue
        old_req = Requirement(old)
        new_req = update_requirement(old_req, lockfile)
        if old_req != new_req:
            reqs[i] = str(new_req)


def _toml_get_table(
    container: _TomlContainer | tomlkit.items.AbstractTable, key: str
) -> tomlkit.items.AbstractTable:
    r"""Extract the table at that key, or return a null object table.

    >>> doc = tomlkit.parse("a = 1\nb = {c = 3}")
    >>> _toml_get_table(doc, "b")
    {'c': 3}
    >>> _toml_get_table(doc, "a")
    {}
    >>> _toml_get_table(doc, "nonexistent")
    {}
    """
    try:
        value = container.item(key)
    except NonExistentKey:
        return tomlkit.table()
    if not isinstance(value, tomlkit.items.AbstractTable):
        return tomlkit.table()
    return value


def _toml_get_array(
    container: _TomlContainer | tomlkit.items.AbstractTable, key: str
) -> tomlkit.items.Array:
    r"""Extract the array at that key, or return a null object array.

    >>> doc = tomlkit.parse("a = 1\nb = [42]")
    >>> _toml_get_array(doc, "b")
    [42]
    >>> _toml_get_array(doc, "a")
    []
    >>> _toml_get_array(doc, "nonexistent")
    []
    """
    try:
        value = container.item(key)
    except NonExistentKey:
        return tomlkit.array()
    if not isinstance(value, tomlkit.items.Array):
        return tomlkit.array()
    return value
