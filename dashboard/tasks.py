from django.db import DatabaseError

from config.celery import app
from config.settings import logger
from dashboard.models import Share
from dashboard.services.market_data import MarketDataError, get_last_data


@app.task
def update_last_price():
    for share in Share.objects.all():
        try:
            last_price, price_time = get_last_data(share)
            is_trend_high = share.last_price is None or share.last_price <= last_price

            Share.objects.filter(pk=share.pk).update(
                last_price=last_price,
                is_trend_high=is_trend_high,
                updated_at=price_time,
            )
        except (MarketDataError, DatabaseError, IndexError):
            logger.exception("Could not update market data for share %s", share.pk)
