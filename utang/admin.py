from django.contrib import admin

from utang.models import Utang


@admin.register(Utang)
class UtangAdmin(admin.ModelAdmin):
    list_display = ("person", "owner", "direction", "amount", "date", "due_date")
    list_filter = ("direction",)
