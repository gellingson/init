from django.contrib import admin
from listings.models import Listing, Dealership

class DealershipAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['full_name', 'textid', 'base_url', 'inventory_url']}),
        ('Functions', {'fields': ['extract_car_list_func','listing_from_list_item_func', 'parse_listing_func']})]

admin.site.register(Dealership, DealershipAdmin)
admin.site.register(Listing)
