from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase
from uuid import UUID, uuid4
from sqlalchemy import CHAR

class Base(AsyncAttrs, DeclarativeBase):
    id: Mapped[UUID] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=uuid4,
    )

    @hybrid_property
    def reference(self) -> str:
        return str(self.id)