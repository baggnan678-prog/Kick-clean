import enum
from typing import TypeVar

from sqlalchemy import Enum

E = TypeVar("E", bound=enum.Enum)


def str_enum(enum_cls: type[E], *, name: str) -> Enum:
    """Colonne ENUM PostgreSQL qui persiste la .value (ex: "provider") plutôt que
    le .name Python (ex: "PROVIDER") — comportement par défaut de SQLAlchemy que
    l'on ne veut pas ici, car les types ENUM en base utilisent les valeurs métier
    en minuscules."""
    return Enum(enum_cls, name=name, values_callable=lambda obj: [member.value for member in obj])
