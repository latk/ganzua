import typing as t

from packaging.specifiers import Specifier, SpecifierSet


class PrettySpecifierSet(SpecifierSet):
    """Override a SpecifierSet to emit specifiers in a prettier order.

    >>> str(PrettySpecifierSet("<5,>=4"))
    '>=4,<5'
    """

    @t.override
    def __iter__(self) -> t.Iterator[Specifier]:
        # cf https://github.com/pypa/packaging/blob/0055d4b8ff353455f0617690e609bc68a1f9ade2/src/packaging/specifiers.py#L852
        return iter(sorted(super().__iter__(), key=_specifier_sort_key))

    @t.override
    def __str__(self) -> str:
        # cf https://github.com/pypa/packaging/blob/0055d4b8ff353455f0617690e609bc68a1f9ade2/src/packaging/specifiers.py#L775
        return ",".join(str(s) for s in self)


_SPECIFIER_OPERATOR_RANK: t.Final = (">", ">=", "~=", "==", "<=", "<", "!=", "===")


def _specifier_sort_key(spec: Specifier) -> tuple[int, str]:
    """Determine a total order over specifiers, instead of relying on unspecified hash.

    >>> _specifier_sort_key(Specifier(">=4"))
    (1, '4')
    >>> _specifier_sort_key(Specifier("<5"))
    (5, '5')
    >>> _specifier_sort_key(Specifier(">=4")) < _specifier_sort_key(Specifier("<5"))
    True
    """
    try:
        operator_rank = _SPECIFIER_OPERATOR_RANK.index(spec.operator)
    except ValueError:  # pragma: no cover
        operator_rank = 999
    return operator_rank, spec.version
