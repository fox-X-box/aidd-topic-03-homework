from django.db import DatabaseError

from config.celery import app
from config.settings import logger
from dashboard.models import Share
from dashboard.services.market_data import MarketDataError, get_last_data
from dashboard.services.watchlist import process_share_quote


@app.task
def update_last_price():
    for share in Share.objects.all():
        try:
            last_price, price_time = get_last_data(share)
            process_share_quote(share.pk, last_price, price_time)
        except (MarketDataError, DatabaseError, IndexError):
            logger.exception("Could not update market data for share %s", share.pk)
