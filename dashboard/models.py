from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class Share(models.Model):
    """Акция"""

    figi = models.CharField(max_length=255, unique=True)
    isin = models.CharField(max_length=255)
    name = models.CharField(max_length=255, verbose_name="Наименование компании")
    ticker = models.CharField(max_length=10, unique=True, verbose_name="Тикер")
    currency = models.CharField(max_length=20, verbose_name="Валюта")
    uid = models.CharField(max_length=255, unique=True)
    last_price = models.FloatField(blank=True, null=True, verbose_name="Текущая цена")
    is_trend_high = models.BooleanField(
        blank=True, null=True, verbose_name="Растет цена"
    )
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"


class WatchlistItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
    )
    share = models.ForeignKey(Share, on_delete=models.CASCADE, related_name="watchers")
    target_price = models.DecimalField(
        max_digits=20,
        decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
    )
    is_above_target = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["share__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "share"], name="unique_user_watchlist_share"
            ),
            models.CheckConstraint(
                check=Q(target_price__gt=0), name="watchlist_target_positive"
            ),
        ]

    def __str__(self):
        return f"{self.user}: {self.share} at {self.target_price}"


class PriceAlert(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="price_alerts",
    )
    share = models.ForeignKey(
        Share, on_delete=models.SET_NULL, null=True, related_name="price_alerts"
    )
    share_name = models.CharField(max_length=255)
    ticker = models.CharField(max_length=10)
    target_price = models.DecimalField(max_digits=20, decimal_places=9)
    triggered_price = models.DecimalField(max_digits=20, decimal_places=9)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"{self.ticker}: {self.triggered_price} >= {self.target_price}"
