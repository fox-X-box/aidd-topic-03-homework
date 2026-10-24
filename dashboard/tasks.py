import logging
from django.conf import settings
from config.celery import app
from dashboard.models import Share
from dashboard.services.market_data import get_last_data, MarketDataError

logger = logging.getLogger(__name__)


@app.task
def update_last_price():
    if not settings.TINKOFF_TOKEN:
        return {'updated': 0, 'failed': 0, 'skipped': 'TINKOFF_TOKEN is not configured'}
    updated = failed = 0
    for share in Share.objects.iterator():
        try:
            price, observed_at = get_last_data(share)
            Share.objects.filter(pk=share.pk).update(last_price=price,
                is_trend_high=share.last_price is None or price >= share.last_price,
                updated_at=observed_at)
            updated += 1
        except MarketDataError:
            logger.warning('Could not refresh share %s', share.pk)
            failed += 1
    return {'updated': updated, 'failed': failed}
