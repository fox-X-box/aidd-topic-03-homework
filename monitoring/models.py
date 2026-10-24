from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Watchlist(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField("Название списка", max_length=100)

    class Meta:
        ordering = ("name", "pk")
        constraints = [
            models.UniqueConstraint(fields=("owner", "name"), name="unique_owner_watchlist")
        ]

    def __str__(self):
        return self.name


class WatchRule(models.Model):
    class Direction(models.TextChoices):
        ABOVE = "above", "Цена не ниже цели"
        BELOW = "below", "Цена не выше цели"

    watchlist = models.ForeignKey(Watchlist, on_delete=models.CASCADE, related_name="rules")
    share = models.ForeignKey("dashboard.Share", on_delete=models.CASCADE)
    direction = models.CharField("Условие", max_length=5, choices=Direction.choices)
    target_price = models.DecimalField(
        "Целевая цена", max_digits=24, decimal_places=9,
        validators=[MinValueValidator(Decimal("0.000000001"))],
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.CheckConstraint(condition=models.Q(target_price__gt=0), name="watch_target_positive")
        ]


class Notification(models.Model):
    # Deleting a rule/list leaves the already delivered notification in the inbox.
    rule = models.OneToOneField(
        WatchRule, null=True, blank=True, on_delete=models.SET_NULL, related_name="notification"
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ticker = models.CharField(max_length=10)
    currency = models.CharField(max_length=20)
    direction = models.CharField(max_length=5, choices=WatchRule.Direction.choices)
    target_price = models.DecimalField(max_digits=24, decimal_places=9)
    observed_price = models.DecimalField(max_digits=24, decimal_places=9)
    observed_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ("-created_at", "-pk")
