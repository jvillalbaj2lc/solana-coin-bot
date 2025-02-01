# app/database/models.py

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from app.database.base import Base

class TokenSnapshot(Base):
    """
    Represents a snapshot of token data at a specific moment in time.
    """
    __tablename__ = 'token_snapshots'

    id = Column(Integer, primary_key=True, index=True)
    token_address = Column(String, index=True, nullable=False)
    chain_id = Column(String, nullable=True)
    icon = Column(String, nullable=True)
    description = Column(String, nullable=True)
    # Example of storing a list of link objects. For SQLite,
    # SQLAlchemy typically stores JSON as text under the hood.
    links = Column(JSON, nullable=True)
    price_usd = Column(Float, nullable=True)
    liquidity = Column(Float, nullable=True)
    volume_usd = Column(Float, nullable=True)
    developer = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self) -> str:
        return (f"<TokenSnapshot(id={self.id}, token_address={self.token_address}, "
                f"price_usd={self.price_usd}, timestamp={self.timestamp})>")
