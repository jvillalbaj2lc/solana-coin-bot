# app/database/models.py

from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Text
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.sql import func

from app.database.base import Base

class TokenSnapshot(Base):
    """
    Represents a snapshot of token data from DexScreener.
    Stores both the token profile and any additional metrics/risk data.
    """
    __tablename__ = "token_snapshots"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Token Profile Data (from DexScreener)
    token_address = Column(String(255), nullable=False, index=True)
    chain_id = Column(String(50), nullable=False)
    token_name = Column(String(255))
    token_symbol = Column(String(50))
    dexscreener_url = Column(String(512))
    icon_url = Column(String(512))
    header_url = Column(String(512))
    open_graph_url = Column(String(512))
    description = Column(Text)
    
    # Token Links (social media, website, etc.)
    links = Column(MutableDict.as_mutable(JSON))
    
    # Market Data
    price_usd = Column(Float)
    liquidity_usd = Column(Float)
    volume_usd = Column(Float)
    
    # Risk Assessment Data
    risk_data = Column(MutableDict.as_mutable(JSON))

    def to_dict(self) -> Dict[str, Any]:
        """Convert the snapshot to a dictionary."""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'token_address': self.token_address,
            'chain_id': self.chain_id,
            'token_name': self.token_name,
            'token_symbol': self.token_symbol,
            'dexscreener_url': self.dexscreener_url,
            'icon_url': self.icon_url,
            'header_url': self.header_url,
            'open_graph_url': self.open_graph_url,
            'description': self.description,
            'links': self.links,
            'price_usd': self.price_usd,
            'liquidity_usd': self.liquidity_usd,
            'volume_usd': self.volume_usd,
            'risk_data': self.risk_data
        }

    @classmethod
    def from_token_profile(
        cls,
        profile: 'TokenProfile',
        price_usd: Optional[float] = None,
        liquidity_usd: Optional[float] = None,
        volume_usd: Optional[float] = None,
        risk_data: Optional[Dict[str, Any]] = None
    ) -> 'TokenSnapshot':
        """
        Create a TokenSnapshot from a DexScreener TokenProfile.
        
        :param profile: TokenProfile instance
        :param price_usd: Current price in USD
        :param liquidity_usd: Current liquidity in USD
        :param volume_usd: Current volume in USD
        :param risk_data: Optional risk assessment data
        :return: TokenSnapshot instance
        """
        # Convert links list to a dictionary with indices as keys
        links_dict = {}
        if profile.links:
            for idx, link in enumerate(profile.links):
                links_dict[str(idx)] = {
                    'url': link.url,
                    **({"type": link.type} if link.type else {}),
                    **({"label": link.label} if link.label else {})
                }
        
        return cls(
            token_address=profile.token_address,
            chain_id=profile.chain_id,
            token_name=profile.name,
            token_symbol=profile.symbol,
            dexscreener_url=profile.url,
            icon_url=profile.icon,
            header_url=profile.header,
            open_graph_url=profile.open_graph,
            description=profile.description,
            links=links_dict,
            price_usd=price_usd,
            liquidity_usd=liquidity_usd,
            volume_usd=volume_usd,
            risk_data=risk_data
        )
