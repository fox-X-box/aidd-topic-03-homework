from decimal import Decimal, InvalidOperation, localcontext

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Strategy(models.Model):
    class Side(models.TextChoices):
        BUY = "buy", "Купить при цене не выше порога"
        SELL = "sell", "Продать при цене не ниже порога"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает условия"
        EXECUTED = "executed", "Исполнена"
        FAILED = "failed", "Ошибка исполнения"
        CANCELLED = "cancelled", "Отменена"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    portfolio = models.ForeignKey("portfolio.Portfolio", on_delete=models.PROTECT)
    share = models.ForeignKey("dashboard.Share", on_delete=models.PROTECT)
    name = models.CharField("Название", max_length=120)
    side = models.CharField("Условие", max_length=4, choices=Side.choices)
    quantity = models.DecimalField("Количество", max_digits=20, decimal_places=8,
                                   validators=[MinValueValidator(Decimal("0.00000001"))])
    price_threshold = models.DecimalField("Порог цены", max_digits=24, decimal_places=9,
                                         validators=[MinValueValidator(Decimal("0.000000001"))])
    enabled = models.BooleanField(default=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="strategy_positive_quantity"),
            models.CheckConstraint(condition=models.Q(price_threshold__gt=0), name="strategy_positive_price"),
        ]

    def clean(self):
        super().clean()
        if self.portfolio_id and self.owner_id and self.portfolio.owner_id != self.owner_id:
            raise ValidationError("Портфель должен принадлежать владельцу стратегии.")
        if self.portfolio_id and self.share_id:
            if self.portfolio.currency.lower() != self.share.currency.lower():
                raise ValidationError("Валюта акции должна совпадать с валютой портфеля.")

    def __str__(self):
        return self.name


class StrategyExecution(models.Model):
    strategy = models.OneToOneField(Strategy, on_delete=models.CASCADE, related_name="execution")
    trade = models.OneToOneField("portfolio.Trade", on_delete=models.PROTECT, null=True, blank=True)
    price = models.DecimalField(max_digits=24, decimal_places=9)
    observed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    error = models.TextField(blank=True)

    @property
    def result(self):
        """Sale P&L or hypothetical price movement of the original purchased lot.

        Purchases deliberately do not claim actual portfolio profit after later
        sales: their metric asks what that lot would be worth if still held.
        """
        if not self.trade_id:
            return None
        if self.strategy.side == Strategy.Side.SELL:
            return self.trade.realized_pnl
        current = self.strategy.share.last_price
        if current is None:
            return None
        try:
            current = Decimal(str(current))
            if not current.is_finite() or current < 0:
                return None
            with localcontext() as context:
                context.prec = 60
                return (current - self.trade.price) * self.trade.quantity
        except (InvalidOperation, ValueError, TypeError):
            return None

    @property
    def result_percent(self):
        """Return relative to purchase cost, never relative to sale proceeds."""
        result = self.result
        if result is None:
            return None
        with localcontext() as context:
            context.prec = 60
            cost = self.trade.price * self.trade.quantity
            if self.strategy.side == Strategy.Side.SELL:
                cost -= self.trade.realized_pnl
            return result / cost * 100 if cost > 0 else None
