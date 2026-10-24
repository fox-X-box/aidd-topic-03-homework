from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


class Portfolio(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField("Название", max_length=100)
    currency = models.CharField("Валюта", max_length=20, default="rub")
    initial_cash = models.DecimalField(
        "Начальный капитал", max_digits=29, decimal_places=9,
        default=Decimal("100000"), validators=[MinValueValidator(0)],
    )
    cash = models.DecimalField(max_digits=29, decimal_places=9, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(cash__gte=0), name="portfolio_nonnegative_cash"),
            models.CheckConstraint(condition=models.Q(initial_cash__gte=0), name="portfolio_nonnegative_initial_cash"),
        ]

    def __str__(self):
        return self.name


class Position(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="positions")
    share = models.ForeignKey("dashboard.Share", on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=25, decimal_places=9, default=0)
    average_price = models.DecimalField(max_digits=25, decimal_places=9, default=0)

    class Meta:
        ordering = ["share__ticker"]
        constraints = [
            models.UniqueConstraint(fields=["portfolio", "share"], name="one_position_per_share"),
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="position_nonnegative_quantity"),
            models.CheckConstraint(condition=models.Q(average_price__gte=0), name="position_nonnegative_cost"),
        ]


class Trade(models.Model):
    class Side(models.TextChoices):
        BUY = "buy", "Покупка"
        SELL = "sell", "Продажа"

    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name="trades")
    share = models.ForeignKey("dashboard.Share", on_delete=models.PROTECT)
    side = models.CharField(max_length=4, choices=Side.choices)
    quantity = models.DecimalField(max_digits=25, decimal_places=9)
    price = models.DecimalField(max_digits=25, decimal_places=9)
    realized_pnl = models.DecimalField(max_digits=29, decimal_places=9, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    idempotency_key = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["portfolio", "idempotency_key"], name="unique_portfolio_trade_request"),
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="trade_positive_quantity"),
            models.CheckConstraint(condition=models.Q(price__gt=0), name="trade_positive_price"),
            models.CheckConstraint(condition=models.Q(side__in=["buy", "sell"]), name="trade_valid_side"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Операции портфеля нельзя изменять.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Операции портфеля нельзя удалять.")
