from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from portfolio.services import execute_trade
from .models import Strategy, StrategyExecution


def evaluate_strategies(share, price, observed_at=None):
    """Execute each enabled threshold at most once, using the observed market price.

    A failed business condition consumes the one-shot rule and records its reason.
    Unexpected infrastructure errors propagate so the caller can retry safely.
    """
    try:
        price = Decimal(str(price))
        if (not price.is_finite() or price <= 0 or price >= Decimal("1e15")
                or price != price.quantize(Decimal("0.000000001"))):
            raise ValueError
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError(
            "Цена должна быть положительным числом меньше 10¹⁵ с точностью до 9 знаков."
        ) from exc
    if observed_at is None:
        observed_at = timezone.now()
    if not isinstance(observed_at, datetime) or timezone.is_naive(observed_at):
        raise ValidationError("Время котировки должно содержать часовой пояс.")
    ids = list(Strategy.objects.filter(share=share, enabled=True, status=Strategy.Status.PENDING)
               .values_list("pk", flat=True))
    executions = []
    for pk in ids:
        with transaction.atomic():
            strategy = Strategy.objects.select_for_update().filter(pk=pk).first()
            if strategy is None:
                continue
            if not strategy.enabled or strategy.status != Strategy.Status.PENDING:
                continue
            matches = (
                strategy.side == Strategy.Side.BUY and price <= strategy.price_threshold
                or strategy.side == Strategy.Side.SELL and price >= strategy.price_threshold
            )
            if not matches:
                continue
            trade = None
            error = ""
            try:
                strategy.clean()
                trade = execute_trade(strategy.portfolio, share, strategy.side,
                                      strategy.quantity, price,
                                      idempotency_key=f"strategy:{strategy.pk}")
            except ValidationError as exc:
                error = "; ".join(exc.messages)
            execution = StrategyExecution.objects.create(
                strategy=strategy, trade=trade, price=price, observed_at=observed_at, error=error
            )
            strategy.enabled = False
            strategy.status = Strategy.Status.FAILED if error else Strategy.Status.EXECUTED
            strategy.save(update_fields=["enabled", "status"])
            executions.append(execution)
    return executions
