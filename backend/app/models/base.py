from sqlalchemy import CheckConstraint, MetaData
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData(schema="app")


def named_check(name: str, expression: str) -> CheckConstraint:
    return CheckConstraint(expression, name=name)
