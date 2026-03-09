from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import Column, String, Integer
from database import Base


class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
