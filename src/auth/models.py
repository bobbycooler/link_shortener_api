from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import Column, String, Integer

from src.database import Base


class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "user"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
