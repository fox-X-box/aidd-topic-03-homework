from config.celery import app
from dashboard.models import Share
from dashboard.services.market_data import get_last_data
from config.settings import logger


@app.task
def update_last_price():
    shares = Share.objects.all()

    for share in shares:
        try:
            data = get_last_data(share)
            if data is None:
                logger.warning(
                    f"Пропуск обновления цены для акции {share.id}: "
                    "рыночные данные недоступны"
                )
                continue
            [last_price, detetime] = data

            try:
                if share.last_price is not None and share.last_price > last_price:
                    is_trend_high = False
                else:
                    is_trend_high = True
            except Exception as e:
                logger.error(e)
                is_trend_high = True

            Share.objects.filter(id=share.id).update(
                last_price=last_price, is_trend_high=is_trend_high
            )
        except Exception as e:
            # При любой ошибке получения/обновления цена в БД не меняется.
            logger.error(e)
