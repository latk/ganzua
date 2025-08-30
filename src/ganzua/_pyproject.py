import typing as t
from dataclasses import dataclass

import tomlkit
import tomlkit.container
import tomlkit.items
from packaging.requirements import Requirement as Pep508Requirement
from tomlkit.exceptions import NonExistentKey

from ._constraints import EditRequirement, Requirement, parse_requirement_from_pep508
from ._pretty_specifier_set import PrettySpecifierSet

_TomlDict: t.TypeAlias = (
    tomlkit.container.Container
    | tomlkit.container.OutOfOrderTableProxy
    | tomlkit.items.AbstractTable
)


def edit_pyproject(pyproject: tomlkit.TOMLDocument, mapper: EditRequirement) -> None:
    """Apply the callback to each requirement specifier in the pyproject.toml file."""
    _Editor(pyproject).apply(mapper)


@dataclass
class _Editor:
    # TODO skip path dependencies?
    # TODO support Poetry-specific fields
    # TODO check if there are uv-specific fields
    # TODO support build dependencies?

    pyproject: tomlkit.TOMLDocument

    def __post_init__(self) -> None:
        self.project = _toml_get_table(self.pyproject, "project")
        self.poetry = _toml_get_table(_toml_get_table(self.pyproject, "tool"), "poetry")

    def apply(self, edit: EditRequirement) -> None:
        self._apply_all_pep621(edit)
        self._apply_all_poetry(edit)

    def _apply_all_pep621(self, edit: EditRequirement) -> None:
        self._apply_requirements_array(
            _toml_get_array(self.project, "dependencies"), edit
        )

        optional_dependencies = _toml_get_table(self.project, "optional-dependencies")
        for extra in optional_dependencies:
            extra_dependencies = _toml_get_array(optional_dependencies, extra)
            self._apply_requirements_array(extra_dependencies, edit)

        # dependency groups, see <https://peps.python.org/pep-0735/>
        dependency_groups = _toml_get_table(self.pyproject, "dependency-groups")
        for group in dependency_groups:
            group_dependencies = _toml_get_array(dependency_groups, group)
            self._apply_requirements_array(group_dependencies, edit)

    def _apply_requirements_array(
        self, reqs: tomlkit.items.Array, edit: EditRequirement
    ) -> None:
        for i, item in enumerate(list(reqs)):
            if not isinstance(item, str):
                continue
            req = Pep508Requirement(item)
            data = parse_requirement_from_pep508(req)
            edit.apply(data, kind="pep508")
            new_specifier = PrettySpecifierSet(data["specifier"])
            if req.specifier != new_specifier:
                req.specifier = new_specifier
                reqs[i] = str(req)

    def _apply_all_poetry(self, edit: EditRequirement) -> None:
        # cf https://python-poetry.org/docs/pyproject/#dependencies-and-dependency-groups
        dependencies = _toml_get_table(self.poetry, "dependencies")
        self._apply_poetry_dependency_table(dependencies, edit)

        groups = _toml_get_table(self.poetry, "group")
        for group in groups:
            group_dependencies = _toml_get_table(
                _toml_get_table(groups, group), "dependencies"
            )
            self._apply_poetry_dependency_table(group_dependencies, edit)

    def _apply_poetry_dependency_table(
        self, reqs: _TomlDict, edit: EditRequirement
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
            req = Requirement(name=name, specifier=value.value)
            edit.apply(req, kind="poetry")
            if value.value != req["specifier"]:
                target_table[target_key] = req["specifier"]


def _toml_get_table(container: _TomlDict, key: str) -> _TomlDict:
    r"""Extract the table at that key, or return a null object table.

    >>> doc = tomlkit.parse("a = 1\nb = {c = 3}")
    >>> _toml_get_table(doc, "b")
    {'c': 3}
    >>> _toml_get_table(doc, "a")
    {}
    >>> _toml_get_table(doc, "nonexistent")
    {}

    This function can also extract interrupted tables, which involves a proxy type.
    >>> doc = tomlkit.parse(
    ...     '''\
    ...     [table.a]
    ...     content = 1
    ...     [interrupted]
    ...     [table.b]
    ...     content = 2
    ...     '''
    ... )
    >>> _toml_get_table(doc, "table")
    {'a': {'content': 1}, 'b': {'content': 2}}

    """
    try:
        value = container[key]
    except NonExistentKey:
        return tomlkit.table()
    if not isinstance(value, _TomlDict):
        return tomlkit.table()
    return value


def _toml_get_array(container: _TomlDict, key: str) -> tomlkit.items.Array:
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
        value = container[key]
    except NonExistentKey:
        return tomlkit.array()
    if not isinstance(value, tomlkit.items.Array):
        return tomlkit.array()
    return value
