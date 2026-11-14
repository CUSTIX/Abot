from django.contrib import admin

from paluwagan.models import Paluwagan


@admin.register(Paluwagan)
class PaluwaganAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "share", "members", "my_turn", "frequency", "start_date")
