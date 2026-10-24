from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Notification, WatchRule


def evaluate_alerts(share, price, observed_at=None):
    """Deliver one inbox notification per matching rule, including equal prices.

    Invoked by the market-price ingestion service for each accepted observation.
    Row locks serialize evaluation; the OneToOne constraint is a second guard
    against duplicate delivery. A rule fires once in its lifetime.
    """
    try:
        price = Decimal(str(price))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError("Цена должна быть положительным конечным числом.") from exc
    if not price.is_finite() or price <= 0 or price >= Decimal("1e15"):
        raise ValidationError("Цена должна быть положительным конечным числом меньше 10^15.")
    if price != price.quantize(Decimal("0.000000001")):
        raise ValidationError("Цена может содержать не более 9 знаков после запятой.")
    observed_at = observed_at or timezone.now()
    if timezone.is_naive(observed_at):
        raise ValidationError("Время наблюдения должно содержать часовой пояс.")
    created_count = 0
    with transaction.atomic():
        rules = (
            WatchRule.objects.select_for_update(of=("self",))
            .select_related("watchlist")
            .filter(share=share, notification__isnull=True)
            .filter(
                Q(direction=WatchRule.Direction.ABOVE, target_price__lte=price)
                | Q(direction=WatchRule.Direction.BELOW, target_price__gte=price)
            )
            .order_by("pk")
        )
        for rule in rules:
            _, created = Notification.objects.get_or_create(
                rule=rule,
                defaults={
                    "owner_id": rule.watchlist.owner_id,
                    "ticker": share.ticker,
                    "currency": share.currency,
                    "direction": rule.direction,
                    "target_price": rule.target_price,
                    "observed_price": price,
                    "observed_at": observed_at,
                },
            )
            created_count += int(created)
    return created_count
