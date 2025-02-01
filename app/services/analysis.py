# app/services/analysis.py

import logging
import datetime
import pandas as pd
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from app.database.models import TokenSnapshot

logger = logging.getLogger(__name__)

def analyze_token_trends(
    session: Session,
    config: Dict[str, Any],
    lookback_hours: int = 6,
    price_increase_threshold: float = 50.0
) -> List[Tuple[str, float]]:
    """
    Analyzes historical token snapshots to detect large price pumps over the given lookback period.
    Specifically, it flags tokens whose price has increased by more than 'price_increase_threshold'
    percent in the last 'lookback_hours' hours.

    Steps:
    1) Query token snapshots from the DB for the last 'lookback_hours'.
    2) Convert to a DataFrame and group by token address.
    3) For each token, find the earliest and latest price in that period.
    4) Calculate percentage change. If above threshold, flag the token.

    :param session: SQLAlchemy Session object.
    :param config:  The application config dictionary (if needed for thresholds or filtering).
    :param lookback_hours: How many hours back to look for data.
    :param price_increase_threshold: Minimum % increase to consider a "pump."
    :return: A list of tuples: [(token_address, percentage_increase), ...]
    """

    # 1) Determine the cutoff time
    now = datetime.datetime.utcnow()
    cutoff_time = now - datetime.timedelta(hours=lookback_hours)

    # 2) Query the relevant snapshots from the DB
    #    We only retrieve snapshots from the last X hours to reduce data load
    snapshots_q = (
        session.query(TokenSnapshot)
        .filter(TokenSnapshot.timestamp >= cutoff_time)
        .order_by(TokenSnapshot.timestamp.asc())
    )
    snapshots = snapshots_q.all()

    if not snapshots:
        logger.info("No snapshots found in the last %d hours.", lookback_hours)
        return []

    # Convert to a DataFrame
    records = []
    for snap in snapshots:
        records.append({
            "token_address": snap.token_address,
            "price_usd": snap.price_usd,
            "timestamp": snap.timestamp
        })
    df = pd.DataFrame(records)

    # 3) Sort by timestamp for each token
    df.sort_values("timestamp", inplace=True)

    # 4) Group by token and compute earliest & latest price in the period
    flagged = []
    for token_addr, group in df.groupby("token_address"):
        if len(group) < 2:
            # Not enough data points to compare
            continue

        # Earliest price in this lookback window
        first_price = group.iloc[0]["price_usd"]
        # Latest price
        last_price = group.iloc[-1]["price_usd"]

        # Validate we have numeric values
        if first_price is None or last_price is None:
            continue
        if first_price <= 0:
            continue

        # Calculate percentage change
        pct_change = ((last_price - first_price) / first_price) * 100.0

        # 5) If above threshold, flag the token
        if pct_change >= price_increase_threshold:
            flagged.append((token_addr, pct_change))

    if flagged:
        logger.info("Found %d tokens above the price-increase threshold.", len(flagged))
    else:
        logger.info("No tokens flagged for a pump > %.2f%% in the last %d hours.",
                    price_increase_threshold, lookback_hours)

    return flagged
