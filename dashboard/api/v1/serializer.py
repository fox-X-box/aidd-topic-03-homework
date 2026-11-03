import uuid

from rest_framework import serializers

from dashboard.models import Share


class ShareSerializer(serializers.ModelSerializer):
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
        read_only_fields = ("id", "updated_at", "uid")

    def create(self, validated_data):
        # uid обязателен в модели, но не приходит от клиента — генерируем автоматически.
        if not validated_data.get("uid"):
            validated_data["uid"] = str(uuid.uuid4())
        return super().create(validated_data)
