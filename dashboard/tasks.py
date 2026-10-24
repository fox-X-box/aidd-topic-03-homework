import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from config.celery import app
from dashboard.models import Share
from dashboard.services.market_data import get_last_data, MarketDataError
from dashboard.services.prices import record_price

logger = logging.getLogger(__name__)


@app.task
def update_last_price():
    if not settings.TINKOFF_TOKEN:
        return {'updated': 0, 'failed': 0, 'skipped': 'TINKOFF_TOKEN is not configured'}
    updated = failed = 0
    for share in Share.objects.iterator():
        try:
            price, observed_at = get_last_data(share)
            record_price(share, price, observed_at)
            updated += 1
        except (MarketDataError, ValidationError):
            logger.warning('Could not refresh share %s', share.pk)
            failed += 1
    return {'updated': updated, 'failed': failed}
