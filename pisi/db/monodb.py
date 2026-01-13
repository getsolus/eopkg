import os

from sqlalchemy import create_engine, ForeignKey, String, Integer
from sqlalchemy.orm import Session, DeclarativeBase, Mapped, mapped_column, relationship
from typing import List, Optional

DB_PATH='./db.sqlite'


engine = create_engine(f'sqlite:///{DB_PATH}', echo=True)


class Base(DeclarativeBase):
    pass


class Package(Base):
    __tablename__ = 'packages'
    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    component: Mapped[str] = mapped_column(String(50))


class Dependency(Base):
    __tablename__ = 'dependencies'

    minimum_release: Mapped[int] = mapped_column(Integer, primary_key=True)
    package: relationship(Package, backref='reverse_dependencies')


def build_db():
    os.unlink(DB_PATH)
    Base.metadata.create_all(engine)
    eopkg = Package(name='eopkg', component='system.base')
    pisi = Package(name='pisi', component='fkoff')
    with Session(engine) as session:
        session.add(pisi)
        session.add(eopkg)
        session.commit()
    def __repr__(self) -> str:
        return f"Package(name={self.name!r}, component={self.component!r})"
