from django.contrib import admin

from money.models import Category, Transaction, Wallet


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "kind", "spendable", "archived")
    list_filter = ("kind", "archived")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "kind", "archived")
    list_filter = ("kind",)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "owner", "kind", "amount", "wallet", "category")
    list_filter = ("kind",)
    list_select_related = ("owner", "wallet", "category")
