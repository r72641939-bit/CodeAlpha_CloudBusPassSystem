"""
Per-caller limits kept in the database, so they hold across serverless
instances (in-memory counters would not).
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import RateEvent

logger = logging.getLogger(__name__)


def recent_events(db: Session, key: str, window: timedelta) -> int:
    return db.scalar(
        select(func.count()).select_from(RateEvent).where(
            RateEvent.key == key, RateEvent.created_at > datetime.utcnow() - window
        )
    )


def record_event(db: Session, key: str) -> None:
    """Saves one event and drops this caller's events older than a day."""
    db.add(RateEvent(key=key))
    db.execute(delete(RateEvent).where(
        RateEvent.key == key, RateEvent.created_at < datetime.utcnow() - timedelta(days=1)
    ))
    db.commit()
