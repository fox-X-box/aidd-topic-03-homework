"""Persist quotes exactly once, then evaluate personal rules and virtual trades."""
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from dashboard.models import PricePoint, Share


def record_price(share, price, observed_at=None):
    try:
        price = Decimal(str(price))
        if not price.is_finite() or price <= 0 or price >= Decimal('1e15') or price != price.quantize(Decimal('0.000000001')):
            raise ValueError
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('Цена должна быть положительным числом с точностью до 9 знаков.')
    observed_at = observed_at or timezone.now()
    if timezone.is_naive(observed_at):
        raise ValidationError('Время котировки должно содержать часовой пояс.')
    with transaction.atomic():
        locked = Share.objects.select_for_update().get(pk=share.pk)
        latest = locked.price_history.order_by('-observed_at').first()
        point, created = PricePoint.objects.get_or_create(share=locked, observed_at=observed_at, defaults={'price': price})
        if point.price != price:
            raise ValidationError('Для этого времени уже записана другая цена.')
        # Duplicates and backfill never execute current orders or regress the quote.
        if not created or (latest and observed_at < latest.observed_at):
            return point, created
        trend = locked.last_price is None or price >= locked.last_price
        Share.objects.filter(pk=locked.pk).update(last_price=price, is_trend_high=trend, updated_at=observed_at)
        from monitoring.services import evaluate_alerts
        from strategies.services import evaluate_strategies
        evaluate_alerts(locked, price, observed_at)
        evaluate_strategies(locked, price, observed_at)
    return point, created
