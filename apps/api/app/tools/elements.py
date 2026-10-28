"""The first 36 elements: symbol, name, proton number, group and period. Deterministic reference data, like the
units table — a Chemistry diagram takes its proton number and electron shells from here, never from a model.

Groups are numbered as the 0620 syllabus numbers them: I to VII, and VIII for the noble gases; transition elements
have no group number. Electron shells follow the IGCSE rule for the first 20 elements (2, 8, 8, 2); the syllabus
asks for configurations only up to calcium, so none is given beyond it.
"""

from __future__ import annotations

from dataclasses import dataclass

GROUP_NAMES = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII"}
MAX_CONFIGURED = 20  # configurations are drawn for proton numbers 1 to 20 only


@dataclass(frozen=True)
class Element:
    symbol: str
    name: str
    z: int
    group: int | None  # 1..8 as I..VIII; None for the transition elements
    period: int


_ROWS = [
    ("H", "hydrogen", 1, None, 1),  # placed above Group I on the syllabus's table but not in any group
    ("He", "helium", 2, 8, 1),
    ("Li", "lithium", 3, 1, 2),
    ("Be", "beryllium", 4, 2, 2),
    ("B", "boron", 5, 3, 2),
    ("C", "carbon", 6, 4, 2),
    ("N", "nitrogen", 7, 5, 2),
    ("O", "oxygen", 8, 6, 2),
    ("F", "fluorine", 9, 7, 2),
    ("Ne", "neon", 10, 8, 2),
    ("Na", "sodium", 11, 1, 3),
    ("Mg", "magnesium", 12, 2, 3),
    ("Al", "aluminium", 13, 3, 3),
    ("Si", "silicon", 14, 4, 3),
    ("P", "phosphorus", 15, 5, 3),
    ("S", "sulfur", 16, 6, 3),
    ("Cl", "chlorine", 17, 7, 3),
    ("Ar", "argon", 18, 8, 3),
    ("K", "potassium", 19, 1, 4),
    ("Ca", "calcium", 20, 2, 4),
    ("Sc", "scandium", 21, None, 4),
    ("Ti", "titanium", 22, None, 4),
    ("V", "vanadium", 23, None, 4),
    ("Cr", "chromium", 24, None, 4),
    ("Mn", "manganese", 25, None, 4),
    ("Fe", "iron", 26, None, 4),
    ("Co", "cobalt", 27, None, 4),
    ("Ni", "nickel", 28, None, 4),
    ("Cu", "copper", 29, None, 4),
    ("Zn", "zinc", 30, None, 4),
    ("Ga", "gallium", 31, 3, 4),
    ("Ge", "germanium", 32, 4, 4),
    ("As", "arsenic", 33, 5, 4),
    ("Se", "selenium", 34, 6, 4),
    ("Br", "bromine", 35, 7, 4),
    ("Kr", "krypton", 36, 8, 4),
]
ELEMENTS: dict[str, Element] = {row[0]: Element(*row) for row in _ROWS}
BY_NAME: dict[str, Element] = {e.name: e for e in ELEMENTS.values()}


def find(name_or_symbol: str) -> Element | None:
    """By symbol ("Na", case as written) or by name ("sodium", any case)."""
    text = name_or_symbol.strip()
    return ELEMENTS.get(text) or BY_NAME.get(text.lower())


def shells(electrons: int) -> list[int]:
    """Electron shells for up to 20 electrons: 2, then 8, then 8, then the rest."""
    if not 0 <= electrons <= MAX_CONFIGURED:
        raise ValueError("configurations are given for 0 to 20 electrons only")
    out: list[int] = []
    for capacity in (2, 8, 8, 2):
        if electrons <= 0:
            break
        out.append(min(capacity, electrons))
        electrons -= out[-1]
    return out
