from django.contrib import admin
from trusts.models import Trust, Role, RolePermission, TrustUserPermission

admin.site.register(Trust, admin.ModelAdmin)
admin.site.register(Role, admin.ModelAdmin)
admin.site.register(RolePermission, admin.ModelAdmin)
admin.site.register(TrustUserPermission, admin.ModelAdmin)

