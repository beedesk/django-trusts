from django.contrib import admin
from trusts.models import Trust

admin.site.register(Trust, admin.ModelAdmin)
