import typing as t
from dataclasses import dataclass

import packaging.markers
import packaging.requirements

from . import _toml as toml
from ._edit_requirement import EditRequirement
from ._pretty_specifier_set import PrettySpecifierSet
from ._requirement import (
    Name,
    Requirement,
    normalized_name,
    parse_requirement_from_pep508,
)


def edit_pyproject(pyproject: toml.Ref, mapper: EditRequirement) -> None:
    """Apply the callback to each requirement specifier in the pyproject.toml file."""
    _Editor.new(pyproject).apply(mapper)


@t.final
@dataclass
class _Editor:
    # TODO skip path dependencies?
    # TODO support Poetry-specific fields
    # TODO check if there are uv-specific fields
    # TODO support build dependencies?

    root: toml.Ref

    @classmethod
    def new(cls, pyproject: toml.Ref) -> t.Self:
        return cls(pyproject)

    def __post_init__(self) -> None:
        self.project = self.root["project"]
        self.poetry = self.root["tool"]["poetry"]
        self.dependency_group_rdeps = _dependency_groups_rdeps(
            self.root["dependency-groups"]
        )
        self.poetry_extras_for_package = _poetry_extras_for_package(
            self.poetry["extras"]
        )

    def apply(self, edit: EditRequirement) -> None:
        self._apply_all_pep621(edit)
        self._apply_all_poetry(edit)

    def _apply_all_pep621(self, edit: EditRequirement) -> None:
        for ref in self.project["dependencies"].array_items():
            self._apply_pep508_requirement(ref, edit)

        for extra_ref in self.project["optional-dependencies"].table_entries():
            extra_name = normalized_name(extra_ref.key)
            for ref in extra_ref.array_items():
                self._apply_pep508_requirement(ref, edit, in_extra=extra_name)

        # dependency groups, see <https://peps.python.org/pep-0735/>
        for group_ref in self.root["dependency-groups"].table_entries():
            for ref in group_ref.array_items():
                self._apply_pep508_requirement(
                    ref, edit, group=normalized_name(group_ref.key)
                )

    def _apply_pep508_requirement(
        self,
        ref: toml.Ref,
        edit: EditRequirement,
        *,
        group: Name | None = None,
        in_extra: Name | None = None,
    ) -> None:
        old_requirement = ref.value_as_str()
        if old_requirement is None:
            return

        groups = frozenset[Name]()
        if group:
            groups = frozenset((group, *self.dependency_group_rdeps.get(group, ())))

        new_requirement = apply_one_pep508_edit(
            old_requirement, edit, groups=groups, in_extra=in_extra
        )
        if new_requirement != old_requirement:
            ref.replace(new_requirement)

    def _apply_all_poetry(self, edit: EditRequirement) -> None:
        # cf https://python-poetry.org/docs/pyproject/#dependencies-and-dependency-groups
        self._apply_poetry_dependency_table(
            self.poetry["dependencies"], edit, group=None
        )

        for group_ref in self.poetry["group"].table_entries():
            self._apply_poetry_dependency_table(
                group_ref["dependencies"], edit, group=normalized_name(group_ref.key)
            )

    def _apply_poetry_dependency_table(
        self,
        dependency_table_ref: toml.Ref,
        edit: EditRequirement,
        *,
        group: Name | None,
    ) -> None:
        for item_ref in dependency_table_ref.table_entries():
            name = normalized_name(item_ref.key)
            version_ref: toml.Ref = item_ref
            if "version" in item_ref:
                version_ref = item_ref["version"]
            version = version_ref.value_as_str()
            if version is None:
                continue

            req = Requirement(name=name, specifier=version)

            if extras := frozenset(
                normalized_name(e)
                for ref in item_ref["extras"].array_items()
                if (e := ref.value_as_str()) is not None
            ):
                req["extras"] = extras

            if marker := item_ref["markers"].value_as_str():
                req["marker"] = packaging.markers.Marker(marker)

            if group:
                req["groups"] = frozenset((group,))

            # Requirements in the main (default) group might be part of extras.
            if group is None:
                if in_extras := frozenset(self.poetry_extras_for_package.get(name, [])):
                    req["in_extras"] = in_extras

            edit.apply(req, kind="poetry")
            if version != req["specifier"]:
                version_ref.replace(req["specifier"])


def apply_one_pep508_edit(
    raw_requirement: str,
    edit: EditRequirement,
    *,
    groups: frozenset[Name],
    in_extra: Name | None,
) -> str:
    """Apply an edit to a raw PEP 508 requirement string.

    Returns: the edited requirement, or the input if no change was made.
    """
    req = packaging.requirements.Requirement(raw_requirement)
    data = parse_requirement_from_pep508(req, groups=groups, in_extra=in_extra)
    edit.apply(data, kind="pep508")
    new_specifier = PrettySpecifierSet(data["specifier"])
    if req.specifier == new_specifier:
        return raw_requirement
    req.specifier = new_specifier
    return str(req)


def _dependency_groups_rdeps(dependency_groups_ref: toml.Ref) -> dict[Name, list[Name]]:
    """Build a reverse lookup table for the dependency group graph.

    >>> ref = toml.RefRoot.parse('''
    ... a = ["ignored", { include-group = "c-._._C" }]  # check name normalization
    ... b = ["foo", { include-group = "b" }]
    ... C-c = [{ include-group = "b" }]  # check name normalization
    ... d = [{ include-group = "b" }]
    ... ''')
    >>> _dependency_groups_rdeps(ref)
    {'a': [], 'b': ['a', 'c-c', 'd'], 'c-c': ['a'], 'd': []}

    The spec says that "Dependency Group Includes MUST NOT include cycles"[[1]],
    but since we're only interested in the *set* of referencing groups,
    detecting cycles is more difficult than just finding the transitive closure.

    [1]: https://packaging.python.org/en/latest/specifications/dependency-groups/#dependency-group-include
    """
    # TODO also support `tool.poetry` group includes?
    # <https://python-poetry.org/docs/managing-dependencies/#including-dependencies-from-other-groups>

    def select_includes(items: t.Iterator[toml.Ref]) -> t.Iterator[Name]:
        for ref in items:
            if include := ref["include-group"].value_as_str():
                yield normalized_name(include)

    direct_includes = {
        normalized_name(entry_ref.key): tuple(select_includes(entry_ref.array_items()))
        for entry_ref in dependency_groups_ref.table_entries()
    }

    def transitive_includes(start: Name, *, seen: t.Set[Name]) -> t.Iterator[Name]:
        seen.add(start)
        for direct in direct_includes.get(start, ()):
            if direct in seen:
                continue
            seen.add(direct)
            yield direct
            yield from transitive_includes(direct, seen=seen)

    # build the reverse lookup table
    rdeps: dict[Name, list[Name]] = {group: [] for group in direct_includes}
    for group in direct_includes:
        for dep in transitive_includes(group, seen=set()):
            rdeps.setdefault(dep, []).append(group)
    return rdeps


def _poetry_extras_for_package(extras_ref: toml.Ref) -> dict[Name, list[Name]]:
    """Build a Package -> Extra lookup table from `[tool.poetry.extras]`.

    Docs: https://python-poetry.org/docs/pyproject/#extras

    >>> ref = toml.RefRoot.parse('''
    ... A = ['Pack-1', 'PACK.2']
    ... b = ['pack_2', 'pAck-3', { invalid = 42 }]
    ... c = []
    ... ''')
    >>> _poetry_extras_for_package(ref)
    {'pack-1': ['a'], 'pack-2': ['a', 'b'], 'pack-3': ['b']}
    """
    extras_for_package: dict[Name, list[Name]] = {}
    for extra_ref in extras_ref.table_entries():
        extra_name = normalized_name(extra_ref.key)
        for package_ref in extra_ref.array_items():
            if package := package_ref.value_as_str():
                extras_for_package.setdefault(normalized_name(package), []).append(
                    extra_name
                )
    return extras_for_package
