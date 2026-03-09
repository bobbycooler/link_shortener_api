from sqlalchemy import (BigInteger,
                        Column,
                        Integer,
                        String,
                        ForeignKey,
                        DateTime)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base


class URL(Base):
    __tablename__ = "urls"

    id = Column(Integer, primary_key=True, index=True)
    long_url = Column(String, nullable=False)
    short_url = Column(String,
                       unique=True,
                       index=True,
                       nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_watched_at = Column(DateTime(timezone=True),  nullable=True)

    clicks_count = Column(BigInteger, default=0)

    author_id = Column(Integer,
                       ForeignKey("user.id", ondelete="CASCADE"),
                       nullable=True)

    author = relationship("User", backref="short_url")
