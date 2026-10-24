from rest_framework import serializers
from django.core.exceptions import ValidationError

from dashboard.models import Share


class ShareSerializer(serializers.ModelSerializer):
    def validate_currency(self, value):
        if self.instance:
            try:
                self.instance.validate_currency_change(value)
            except ValidationError as exc:
                raise serializers.ValidationError(exc.messages)
        return value.lower()

    class Meta:
        model = Share
        fields = (
            "id",
            "figi",
            "isin",
            "name",
            "ticker",
            "currency",
            "uid",
            "last_price",
            "is_trend_high",
            "updated_at",
        )

        read_only_fields = ("last_price", "is_trend_high", "updated_at")
