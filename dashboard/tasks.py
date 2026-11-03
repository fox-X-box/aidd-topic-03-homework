from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from config.celery import app
from config.settings import logger
from dashboard.models import Notification, Observation, Share
from dashboard.services.market_data import get_last_data


@app.task
def update_last_price():
    for share in Share.objects.all():
        try:
            data = get_last_data(share)
            if data is None:
                logger.warning("Пропуск обновления цены для акции %s: нет котировки", share.pk)
                continue
            price = Decimal(str(data[0]))
            with transaction.atomic():
                current = Share.objects.select_for_update().get(pk=share.pk)
                current.is_trend_high = current.last_price is None or price >= Decimal(str(current.last_price))
                current.last_price = price
                current.save(update_fields=["last_price", "is_trend_high", "updated_at"])
                check_observations(current.pk, price)
        except Exception:
            logger.exception("Не удалось обновить цену акции %s", share.pk)


def check_observations(share_id, price):
    for observation in Observation.objects.select_for_update().filter(stock_id=share_id):
        reached = price >= observation.target_price
        if reached == observation.target_reached:
            continue
        observation.target_reached = reached
        observation.save(update_fields=["target_reached"])
        if reached:
            Notification.objects.create(
                observation=observation, event_time=timezone.now(),
                target_price=observation.target_price, actual_price=price,
            )
