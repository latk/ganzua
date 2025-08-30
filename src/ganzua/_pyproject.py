import tomlkit
import tomlkit.items
from packaging.requirements import Requirement
from tomlkit.container import Container as _TomlContainer
from tomlkit.exceptions import NonExistentKey

from ._constraints import MapRequirement, PoetryRequirement


def edit_pyproject(pyproject: tomlkit.TOMLDocument, mapper: MapRequirement) -> None:
    """Apply the callback to each requirement specifier in the pyproject.toml file."""
    # TODO skip path dependencies?
    # TODO support Poetry-specific fields
    # TODO check if there are uv-specific fields
    # TODO support build dependencies?

    project = _toml_get_table(pyproject, "project")

    _update_requirements_array(_toml_get_array(project, "dependencies"), mapper)

    optional_dependencies = _toml_get_table(project, "optional-dependencies")
    for extra in optional_dependencies:
        _update_requirements_array(
            _toml_get_array(optional_dependencies, extra), mapper
        )

    dependency_groups = _toml_get_table(pyproject, "dependency-groups")
    for group in dependency_groups:
        _update_requirements_array(_toml_get_array(dependency_groups, group), mapper)

    # cf https://python-poetry.org/docs/pyproject/#dependencies-and-dependency-groups
    poetry = _toml_get_table(_toml_get_table(pyproject, "tool"), "poetry")
    _update_poetry_dependency_table(_toml_get_table(poetry, "dependencies"), mapper)

    poetry_dependency_groups = _toml_get_table(poetry, "group")
    for group in poetry_dependency_groups:
        poetry_group = _toml_get_table(poetry_dependency_groups, group)
        _update_poetry_dependency_table(
            _toml_get_table(poetry_group, "dependencies"), mapper
        )


def _update_requirements_array(
    reqs: tomlkit.items.Array, mapper: MapRequirement
) -> None:
    for i, old in enumerate(list(reqs)):
        if not isinstance(old, str):
            continue
        old_req = Requirement(old)
        new_req = mapper.pep508(old_req)
        if old_req != new_req:
            reqs[i] = str(new_req)


def _update_poetry_dependency_table(
    reqs: tomlkit.items.AbstractTable, mapper: MapRequirement
) -> None:
    name: str
    for name in list(reqs.keys()):
        target_table = reqs
        target_key = name
        value = reqs[name]
        if isinstance(value, tomlkit.items.AbstractTable) and "version" in value:
            target_table = value
            target_key = "version"
            value = value["version"]
        if not isinstance(value, tomlkit.items.String):
            continue
        old_req = PoetryRequirement(name=name, specifier=value.value)
        new_req = mapper.poetry(old_req)
        if old_req != new_req:
            target_table[target_key] = new_req.specifier


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
