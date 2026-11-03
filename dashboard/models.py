from django.db import models
from django.conf import settings


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

    def __str__(self):
        return f"{self.ticker} — {self.name}"

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"


class Observation(models.Model):
    """Наблюдение за акцией пользователем"""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Владелец"
    )
    stock = models.ForeignKey(
        Share, on_delete=models.CASCADE, verbose_name="Акция"
    )
    target_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Целевая цена",
    )
    target_reached = models.BooleanField(
        default=False, verbose_name="Цель достигнута"
    )

    class Meta:
        verbose_name = "Наблюдение"
        verbose_name_plural = "Наблюдения"
        unique_together = ("owner", "stock")


class Notification(models.Model):
    """Уведомление о срабатыании цели"""

    observation = models.ForeignKey(
        Observation, on_delete=models.CASCADE, verbose_name="Наблюдение"
    )
    event_time = models.DateTimeField(verbose_name="Время события")
    target_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Целевая цена"
    )
    actual_price = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Фактическая цена"
    )

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
