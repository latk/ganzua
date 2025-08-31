import typing as t
from dataclasses import dataclass

import tomlkit
import tomlkit.container
import tomlkit.items
from packaging.requirements import Requirement as Pep508Requirement

from ._constraints import EditRequirement, Requirement, parse_requirement_from_pep508
from ._pretty_specifier_set import PrettySpecifierSet
from ._toml import TomlRef, TomlRefRoot


def edit_pyproject(pyproject: tomlkit.TOMLDocument, mapper: EditRequirement) -> None:
    """Apply the callback to each requirement specifier in the pyproject.toml file."""
    _Editor.new(pyproject).apply(mapper)


@t.final
@dataclass
class _Editor:
    # TODO skip path dependencies?
    # TODO support Poetry-specific fields
    # TODO check if there are uv-specific fields
    # TODO support build dependencies?

    root: TomlRef

    @classmethod
    def new(cls, pyproject: tomlkit.TOMLDocument) -> t.Self:
        return cls(TomlRefRoot(pyproject))

    def __post_init__(self) -> None:
        self.project = self.root["project"]
        self.poetry = self.root["tool"]["poetry"]

    def apply(self, edit: EditRequirement) -> None:
        self._apply_all_pep621(edit)
        self._apply_all_poetry(edit)

    def _apply_all_pep621(self, edit: EditRequirement) -> None:
        for ref in self.project["dependencies"].array_items():
            self._apply_pep508_requirement(ref, edit)

        for extra_ref in self.project["optional-dependencies"].table_entries():
            for ref in extra_ref.array_items():
                self._apply_pep508_requirement(ref, edit)

        # dependency groups, see <https://peps.python.org/pep-0735/>
        for group_ref in self.root["dependency-groups"].table_entries():
            for ref in group_ref.array_items():
                self._apply_pep508_requirement(ref, edit)

    def _apply_pep508_requirement(self, ref: TomlRef, edit: EditRequirement) -> None:
        raw_requirement = ref.value_as_str()
        if raw_requirement is None:
            return
        req = Pep508Requirement(raw_requirement)
        data = parse_requirement_from_pep508(req)
        edit.apply(data, kind="pep508")
        new_specifier = PrettySpecifierSet(data["specifier"])
        if req.specifier != new_specifier:
            req.specifier = new_specifier
            ref.replace(str(req))

    def _apply_all_poetry(self, edit: EditRequirement) -> None:
        # cf https://python-poetry.org/docs/pyproject/#dependencies-and-dependency-groups
        self._apply_poetry_dependency_table(self.poetry["dependencies"], edit)

        for group_ref in self.poetry["group"].table_entries():
            self._apply_poetry_dependency_table(group_ref["dependencies"], edit)

    def _apply_poetry_dependency_table(
        self, dependency_table_ref: TomlRef, edit: EditRequirement
    ) -> None:
        for item_ref in dependency_table_ref.table_entries():
            name = item_ref.key
            version_ref: TomlRef = item_ref
            if "version" in item_ref:
                version_ref = item_ref["version"]
            version = version_ref.value_as_str()
            if version is None:
                continue

            req = Requirement(name=name, specifier=version)

            if extras := frozenset(
                e
                for ref in item_ref["extras"].array_items()
                if (e := ref.value_as_str()) is not None
            ):
                req["extras"] = extras

            edit.apply(req, kind="poetry")
            if version != req["specifier"]:
                version_ref.replace(req["specifier"])
