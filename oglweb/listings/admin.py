from django.contrib import admin
from listings.models import Classified, Dealership, Listing, NonCanonicalMake

class ClassifiedAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['full_name', 'textid', 'base_url', 'inventory_url', 'status', 'markers']}),
        ('Functions', {'fields': ['custom_pull_func','extract_car_list_func','listing_from_list_item_func', 'parse_listing_func']})]

class DealershipAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['full_name', 'textid', 'base_url', 'inventory_url', 'status', 'markers']}),
        ('Functions', {'fields': ['extract_car_list_func','listing_from_list_item_func', 'parse_listing_func']})]

class ListingAdmin(admin.ModelAdmin):
    search_fields = ('id','source_textid','model_year','make','model','price')
    fieldsets = [
        ('Status Fields', {'fields': ['status','markers','removal_date','last_update']}),
        ('Listing Fields', {'fields': ['model_year', 'make', 'model', 'source_type', 'source_id', 'source_textid', 'price']}),
        ('Detail Fields', {'fields': ['listing_text','pic_href','listing_href','local_id','stock_no', 'listing_date']})]

class NonCanonicalMakeAdmin(admin.ModelAdmin):
    ordering = ('canonical_name', 'non_canonical_name')
    fieldsets = [
        (None, {'fields': ['non_canonical_name', 'canonical_name', 'consume_words', 'push_words']})]

admin.site.register(Dealership, DealershipAdmin)
admin.site.register(Classified, ClassifiedAdmin)
admin.site.register(Listing, ListingAdmin)
admin.site.register(NonCanonicalMake, NonCanonicalMakeAdmin)
