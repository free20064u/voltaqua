from django.contrib import admin
from .models import Site, Apartment, Meter, Bill, Payment

class ApartmentAdmin(admin.ModelAdmin):
    list_display = ('number', 'site', 'occupants', 'is_active')
    list_filter = ('site', 'is_active')
    search_fields = ('number', 'site__name')
    actions = ['activate_apartments', 'deactivate_apartments']

    def activate_apartments(self, request, queryset):
        queryset.update(is_active=True)
    activate_apartments.short_description = "Activate selected apartments"

    def deactivate_apartments(self, request, queryset):
        queryset.update(is_active=False)
    deactivate_apartments.short_description = "Deactivate selected apartments"

admin.site.register(Apartment, ApartmentAdmin)
admin.site.register(Site)
admin.site.register(Meter)
admin.site.register(Bill)
admin.site.register(Payment)