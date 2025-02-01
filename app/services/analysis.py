# app/services/analysis.py

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from app.database.models import TokenSnapshot

logger = logging.getLogger(__name__)

def analyze_pumped_tokens(
    session: Session,
    lookback_minutes: int = 60,
    min_price_increase_percent: float = 20.0,
    min_volume_usd: float = 1000.0
) -> List[Dict[str, Any]]:
    """
    Analyze token snapshots to detect significant price increases.
    
    :param session: Database session
    :param lookback_minutes: How far back to look for price changes
    :param min_price_increase_percent: Minimum price increase to consider
    :param min_volume_usd: Minimum volume in USD to consider
    :return: List of pumped token details
    """
    cutoff_time = datetime.utcnow() - timedelta(minutes=lookback_minutes)
    
    # Get snapshots ordered by timestamp
    snapshots = (
        session.query(TokenSnapshot)
        .filter(TokenSnapshot.timestamp >= cutoff_time)
        .order_by(TokenSnapshot.timestamp.asc())
        .all()
    )
    
    # Group snapshots by token
    token_snapshots: Dict[str, List[TokenSnapshot]] = {}
    for snapshot in snapshots:
        if snapshot.token_address not in token_snapshots:
            token_snapshots[snapshot.token_address] = []
        token_snapshots[snapshot.token_address].append(snapshot)
    
    # Analyze each token's price movement
    pumped_tokens = []
    for token_address, token_history in token_snapshots.items():
        if len(token_history) < 2:
            continue
            
        # Get first and last snapshots
        first = token_history[0]
        last = token_history[-1]
        
        # Skip if missing required data
        if not (first.price_usd and last.price_usd and last.volume_usd):
            continue
            
        # Calculate price change
        price_change_percent = ((last.price_usd - first.price_usd) / first.price_usd) * 100
        
        # Check if meets pump criteria
        if (price_change_percent >= min_price_increase_percent and 
            last.volume_usd >= min_volume_usd):
            
            # Get risk level if available
            risk_level = "Unknown"
            risk_score = None
            if last.risk_data:
                risk_score = last.risk_data.get('score')
                if risk_score is not None:
                    if risk_score < 500:
                        risk_level = "LOW"
                    elif risk_score < 750:
                        risk_level = "MEDIUM"
                    elif risk_score < 1000:
                        risk_level = "HIGH"
                    else:
                        risk_level = "CRITICAL"
            
            pumped_tokens.append({
                'token_address': token_address,
                'chain_id': last.chain_id,
                'token_name': last.token_name,
                'token_symbol': last.token_symbol,
                'dexscreener_url': last.dexscreener_url,
                'description': last.description,
                'links': last.links,
                'initial_price': first.price_usd,
                'current_price': last.price_usd,
                'price_change_percent': price_change_percent,
                'volume_usd': last.volume_usd,
                'liquidity_usd': last.liquidity_usd,
                'risk_level': risk_level,
                'risk_score': risk_score,
                'risk_data': last.risk_data
            })
    
    return sorted(
        pumped_tokens,
        key=lambda x: x['price_change_percent'],
        reverse=True
    )
