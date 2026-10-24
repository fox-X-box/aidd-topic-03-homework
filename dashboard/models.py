from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Share(models.Model):
    """Акция"""

    figi = models.CharField(max_length=255, unique=True)
    isin = models.CharField(max_length=255)
    name = models.CharField(max_length=255, verbose_name="Наименование компании")
    ticker = models.CharField(max_length=10, unique=True, verbose_name="Тикер")
    currency = models.CharField(max_length=20, verbose_name="Валюта")
    uid = models.CharField(max_length=255, unique=True)
    last_price = models.DecimalField(max_digits=24, decimal_places=9, blank=True, null=True, validators=[MinValueValidator(Decimal("0"))], verbose_name="Текущая цена")
    is_trend_high = models.BooleanField(
        blank=True, null=True, verbose_name="Растет цена"
    )
    updated_at = models.DateTimeField(blank=True, null=True, editable=False)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"


    def validate_currency_change(self, currency):
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).values_list("currency", flat=True).first()
            if old and old.lower() != currency.lower():
                if self.price_history.exists() or self.position_set.exists() or self.trade_set.exists():
                    raise ValidationError("Нельзя менять валюту акции с историей цен или операциями портфеля.")

    def clean(self):
        super().clean()
        self.validate_currency_change(self.currency)

    def save(self, *args, **kwargs):
        self.validate_currency_change(self.currency)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticker} — {self.name}"


class PricePoint(models.Model):
    """A deduplicated market observation, retained for local price charts."""
    share = models.ForeignKey(Share, on_delete=models.CASCADE, related_name="price_history")
    price = models.DecimalField(max_digits=24, decimal_places=9, validators=[MinValueValidator(Decimal("0"))])
    observed_at = models.DateTimeField()

    class Meta:
        ordering = ["observed_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["share", "observed_at"], name="unique_share_observation"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="price_point_nonnegative"),
        ]
