import csv
import datetime as dt

from django.http import HttpResponse
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.api import OwnedViewSet
from money import selectors, services
from money.models import Category, Wallet
from money.serializers import CategorySerializer, TransactionSerializer, WalletSerializer


def _date_param(request, name: str) -> dt.date | None:
    raw = request.query_params.get(name)
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise serializers.ValidationError({name: "Use YYYY-MM-DD."}) from exc


def _int_param(request, name: str) -> int | None:
    raw = request.query_params.get(name)
    if not raw:
        return None
    if not raw.isdigit():
        raise serializers.ValidationError({name: "Must be a number."})
    return int(raw)


class WalletViewSet(OwnedViewSet):
    serializer_class = WalletSerializer
    pagination_class = None  # a handful per person

    def queryset_for(self, user):
        archived = self.request.query_params.get("archived") == "1"
        return selectors.wallets(user, include_archived=archived or self.action != "list")

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "balances": selectors.balances(self.request.user),
        }

    def perform_create(self, serializer):
        serializer.instance = services.save_wallet(
            Wallet(owner=self.request.user, **serializer.validated_data)
        )

    def perform_update(self, serializer):
        wallet = serializer.instance
        for name, value in serializer.validated_data.items():
            setattr(wallet, name, value)
        services.save_wallet(wallet)

    def destroy(self, request, *args, **kwargs):
        outcome = services.delete_wallet(self.get_object())
        if outcome == "archived":
            return Response({"archived": True}, status=status.HTTP_200_OK)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryViewSet(OwnedViewSet):
    serializer_class = CategorySerializer
    pagination_class = None

    def queryset_for(self, user):
        return selectors.categories(user, kind=self.request.query_params.get("kind", ""))

    def perform_create(self, serializer):
        serializer.instance = services.save_category(
            Category(owner=self.request.user, **serializer.validated_data)
        )

    def perform_update(self, serializer):
        category = serializer.instance
        for name, value in serializer.validated_data.items():
            setattr(category, name, value)
        services.save_category(category)

    def perform_destroy(self, instance):
        instance.archived = True  # past transactions keep their category
        instance.save(update_fields=["archived", "updated_at"])


class TransactionViewSet(OwnedViewSet):
    serializer_class = TransactionSerializer

    def queryset_for(self, user):
        q = self.request.query_params
        kind = q.get("kind", "")
        if kind and kind not in ("expense", "income", "transfer"):
            raise serializers.ValidationError({"kind": "expense, income or transfer."})
        return selectors.transactions(
            user,
            kind=kind,
            wallet_id=_int_param(self.request, "wallet"),
            category_id=_int_param(self.request, "category"),
            start=_date_param(self.request, "start"),
            end=_date_param(self.request, "end"),
            search=q.get("q", "")[:60],
        )

    def perform_create(self, serializer):
        txn = services.record(owner=self.request.user, **serializer.validated_data)
        services.learn_keyword(txn.category, txn.note)
        serializer.instance = txn

    def perform_update(self, serializer):
        txn = services.update(serializer.instance, **serializer.validated_data)
        services.learn_keyword(txn.category, txn.note)

    def perform_destroy(self, instance):
        services.delete(instance)


class SpendingView(APIView):
    """Spending per category between two dates (default: this month)."""

    def get(self, request):
        today = timezone.localdate()
        start = _date_param(request, "start") or today.replace(day=1)
        end = _date_param(request, "end") or today
        if end < start or (end - start).days > 366:
            raise serializers.ValidationError({"end": "Pick a range of at most a year."})
        rows = selectors.spending_by_category(request.user, start=start, end=end)
        return Response(
            {
                "start": start,
                "end": end,
                "total": str(sum((r["total"] for r in rows), selectors.ZERO)),
                "categories": [{**r, "total": str(r["total"])} for r in rows],
            }
        )


def _csv_cell(value) -> str:
    """Spreadsheet-safe text: a cell starting with = + - @ (or tab/CR) would run as a formula in
    Excel or Sheets (CSV injection), so it gets a leading apostrophe."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


EXPORT_COLUMNS = ["date", "type", "amount", "wallet", "to_wallet", "category", "note", "neutral"]


class ExportView(APIView):
    """All of your transactions (optionally filtered by date) as a CSV file."""

    def get(self, request):
        start, end = _date_param(request, "start"), _date_param(request, "end")
        rows = selectors.transactions(request.user, start=start, end=end).order_by("date", "id")
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="sahod-transactions.csv"'
        response.write("﻿")  # BOM: Excel opens UTF-8 (₱, ñ, emoji) correctly
        writer = csv.writer(response)
        writer.writerow(EXPORT_COLUMNS)
        for t in rows.iterator():
            writer.writerow(
                [
                    t.date.isoformat(),
                    t.kind,
                    f"{t.amount:.2f}",
                    _csv_cell(t.wallet.name),
                    _csv_cell(t.to_wallet.name if t.to_wallet else ""),
                    _csv_cell(t.category.name if t.category else ""),
                    _csv_cell(t.note),
                    "yes" if t.neutral else "",
                ]
            )
        return response
