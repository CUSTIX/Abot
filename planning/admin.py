from django.contrib import admin

from planning.models import Bill, PaySchedule, SplitRule

admin.site.register(PaySchedule)
admin.site.register(Bill)
admin.site.register(SplitRule)
