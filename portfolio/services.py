"""All simulated trades pass through this transactional ledger."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from .models import Portfolio, Position, Trade

STEP = Decimal("0.000000001")
MAX_VALUE = Decimal("10000000000000000")


def positive_decimal(value, label):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number <= 0 or number >= MAX_VALUE:
            raise InvalidOperation
        rounded = number.quantize(STEP)
        if rounded != number:
            raise InvalidOperation
        return rounded
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"{label}: необходимо положительное число (до 9 знаков после запятой).")


def money(value):
    with localcontext() as context:
        context.prec = 60
        return value.quantize(STEP, rounding=ROUND_HALF_UP)


@transaction.atomic
def execute_trade(portfolio, share, side, quantity, price, *, idempotency_key=None):
    """Execute once, under a portfolio lock. Caller must authorize its owner."""
    quantity = positive_decimal(quantity, "Количество")
    price = positive_decimal(price, "Цена")
    if side not in Trade.Side.values:
        raise ValidationError("Неизвестный тип операции.")
    if idempotency_key is not None and (not idempotency_key or len(idempotency_key) > 200):
        raise ValidationError("Некорректный ключ операции.")
    locked = Portfolio.objects.select_for_update().get(pk=portfolio.pk)
    if idempotency_key is not None:
        previous = locked.trades.filter(idempotency_key=idempotency_key).first()
        if previous:
            if (previous.share_id, previous.side, previous.quantity, previous.price) != (share.pk, side, quantity, price):
                raise ValidationError("Ключ уже использован для другой операции.")
            return previous
    if locked.currency.lower() != share.currency.lower():
        raise ValidationError("Валюта акции должна совпадать с валютой портфеля.")
    position, _ = Position.objects.get_or_create(portfolio=locked, share=share)
    position = Position.objects.select_for_update().get(pk=position.pk)
    with localcontext() as context:
        context.prec = 60
        gross = money(quantity * price)
        if gross <= 0 or gross >= Decimal("1e20"):
            raise ValidationError("Стоимость сделки вне допустимого диапазона.")
        realized_pnl = Decimal(0)
        if side == Trade.Side.BUY:
            if locked.cash < gross:
                raise ValidationError("Недостаточно свободных средств.")
            total = position.quantity + quantity
            if total >= MAX_VALUE:
                raise ValidationError("Количество акций вне допустимого диапазона.")
            position.average_price = money((position.quantity * position.average_price + gross) / total)
            position.quantity = total
            locked.cash -= gross
        else:
            if position.quantity < quantity:
                raise ValidationError("Нельзя продать больше акций, чем есть в портфеле.")
            realized_pnl = money((price - position.average_price) * quantity)
            position.quantity -= quantity
            if position.quantity == 0:
                position.average_price = 0
            locked.cash += gross
            if locked.cash >= Decimal("1e20"):
                raise ValidationError("Баланс вне допустимого диапазона.")
        locked.save(update_fields=["cash"])
        position.save(update_fields=["quantity", "average_price"])
        trade = Trade.objects.create(
            portfolio=locked, share=share, side=side, quantity=quantity, price=price,
            realized_pnl=realized_pnl, idempotency_key=idempotency_key,
        )
    portfolio.cash = locked.cash
    return trade


def portfolio_summary(portfolio):
    """Missing market prices remain unknown instead of silently becoming zero."""
    holdings = []
    current_value = Decimal(0)
    unrealized_pnl = Decimal(0)
    has_missing_prices = False
    for position in portfolio.positions.filter(quantity__gt=0).select_related("share"):
        current = position.share.last_price
        try:
            price = positive_decimal(current, "Котировка")
        except ValidationError:
            price = None
        cost = money(position.quantity * position.average_price)
        value = money(position.quantity * price) if price is not None else None
        pnl = value - cost if value is not None else None
        holdings.append({"position": position, "price": price, "value": value, "cost": cost, "pnl": pnl})
        if value is None:
            has_missing_prices = True
        else:
            current_value += value
            unrealized_pnl += pnl
    realized = portfolio.trades.aggregate(total=Sum("realized_pnl"))["total"] or Decimal(0)
    return {
        "holdings": holdings,
        "has_missing_prices": has_missing_prices,
        "current_value": None if has_missing_prices else current_value,
        "equity": None if has_missing_prices else portfolio.cash + current_value,
        "unrealized_pnl": None if has_missing_prices else unrealized_pnl,
        "realized_pnl": realized,
        "total_pnl": None if has_missing_prices else portfolio.cash + current_value - portfolio.initial_cash,
    }
