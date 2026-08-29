from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Toutes les tables sont créées dans un schema PostgreSQL dédié ("proxiservices")
# pour rester isolées si la base est partagée avec une autre application.
metadata = MetaData(schema="proxiservices")


class Base(DeclarativeBase):
    metadata = metadata
