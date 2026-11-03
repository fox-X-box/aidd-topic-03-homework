from decimal import Decimal

from django.db import transaction

from dashboard.models import PriceAlert, Share, WatchlistItem


@transaction.atomic
def process_share_quote(share_id, quoted_price, quoted_at):
    price = Decimal(str(quoted_price))
    share = Share.objects.select_for_update().get(pk=share_id)
    is_trend_high = share.last_price is None or share.last_price <= float(price)

    Share.objects.filter(pk=share.pk).update(
        last_price=float(price),
        is_trend_high=is_trend_high,
        updated_at=quoted_at,
    )

    watchlist_items = WatchlistItem.objects.select_for_update().filter(
        share_id=share.pk
    )
    for item in watchlist_items:
        is_above_target = price >= item.target_price
        if is_above_target and not item.is_above_target:
            PriceAlert.objects.create(
                user_id=item.user_id,
                share=share,
                share_name=share.name,
                ticker=share.ticker,
                target_price=item.target_price,
                triggered_price=price,
            )

        if item.is_above_target != is_above_target:
            item.is_above_target = is_above_target
            item.save(update_fields=["is_above_target"])
