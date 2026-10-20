"""Static facts about the 16 types (see knowledge/03 and knowledge/04)."""

from __future__ import annotations

TYPES: tuple[str, ...] = (
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
)

# Dominant -> auxiliary -> tertiary -> inferior
STACKS: dict[str, tuple[str, str, str, str]] = {
    "INTJ": ("Ni", "Te", "Fi", "Se"), "INFJ": ("Ni", "Fe", "Ti", "Se"),
    "ISTJ": ("Si", "Te", "Fi", "Ne"), "ISFJ": ("Si", "Fe", "Ti", "Ne"),
    "INTP": ("Ti", "Ne", "Si", "Fe"), "ISTP": ("Ti", "Se", "Ni", "Fe"),
    "INFP": ("Fi", "Ne", "Si", "Te"), "ISFP": ("Fi", "Se", "Ni", "Te"),
    "ENTJ": ("Te", "Ni", "Se", "Fi"), "ESTJ": ("Te", "Si", "Ne", "Fi"),
    "ENFJ": ("Fe", "Ni", "Se", "Ti"), "ESFJ": ("Fe", "Si", "Ne", "Ti"),
    "ENTP": ("Ne", "Ti", "Fe", "Si"), "ENFP": ("Ne", "Fi", "Te", "Si"),
    "ESTP": ("Se", "Ti", "Fe", "Ni"), "ESFP": ("Se", "Fi", "Te", "Ni"),
}

NICKNAMES: dict[str, str] = {
    "INTJ": "The Cartographer", "INTP": "The Puzzler", "ENTJ": "The Helmsman", "ENTP": "The Provocateur",
    "INFJ": "The Seer", "INFP": "The Poet", "ENFJ": "The Kindler", "ENFP": "The Firefly",
    "ISTJ": "The Keystone", "ISFJ": "The Hearthkeeper", "ESTJ": "The Steward", "ESFJ": "The Host",
    "ISTP": "The Fixer", "ISFP": "The Aesthete", "ESTP": "The Daredevil", "ESFP": "The Showstopper",
}

# group key -> (display name, accent colour)
GROUPS: dict[str, tuple[str, str]] = {
    "NT": ("The Minds", "#6E6AE8"),
    "NF": ("The Hearts", "#E0628C"),
    "SJ": ("The Anchors", "#2A9D8F"),
    "SP": ("The Sparks", "#E9A23B"),
}

# (field name in TextAnalysis, first letter, second letter)
AXES: tuple[tuple[str, str, str], ...] = (
    ("e_i", "E", "I"),
    ("s_n", "S", "N"),
    ("t_f", "T", "F"),
    ("j_p", "J", "P"),
)

FUNCTIONS: tuple[str, ...] = ("Ni", "Ne", "Si", "Se", "Ti", "Te", "Fi", "Fe")


def group_of(code: str) -> str:
    if code[1] == "N":
        return "NT" if code[2] == "T" else "NF"
    return "SJ" if code[3] == "J" else "SP"


def types_in(group: str) -> tuple[str, ...]:
    """The four types of a group, in TYPES order."""
    return tuple(code for code in TYPES if group_of(code) == group)
