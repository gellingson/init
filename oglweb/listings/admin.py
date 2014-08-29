from django.contrib import admin
from listings.models import Classified, Dealership, Listing, NonCanonicalMake, NonCanonicalModel, ConceptTag, ConceptImplies

class ClassifiedAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['full_name', 'textid', 'base_url', 'inventory_url', 'status', 'markers']}),
        ('Functions', {'fields': ['custom_pull_func','extract_car_list_func','listing_from_list_item_func', 'parse_listing_func']})]

class DealershipAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['full_name', 'textid', 'base_url', 'inventory_url', 'status', 'markers']}),
        ('Location', {'fields': ['address_line1','address_line2','city','state','zip','lat','lon']}),
        ('More', {'fields': ['phone', 'owner_info', 'owner_account_id', 'license_info', 'primary_dealership_id', 'id']}),
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

class NonCanonicalModelAdmin(admin.ModelAdmin):
    ordering = ('canonical_name', 'non_canonical_name')
    fields = ('non_canonical_make', 'non_canonical_name', 'canonical_name', 'consume_words', 'push_words')

@admin.register(ConceptTag)
class ConceptTagAdmin(admin.ModelAdmin):
    fields = ('tag', 'display_tag', 'syn_of_tag')

@admin.register(ConceptImplies)
class ConceptImpliesAdmin(admin.ModelAdmin):
    fields = ('has_tag', 'implies_tag')

admin.site.register(Dealership, DealershipAdmin)
admin.site.register(Classified, ClassifiedAdmin)
admin.site.register(Listing, ListingAdmin)
admin.site.register(NonCanonicalMake, NonCanonicalMakeAdmin)
admin.site.register(NonCanonicalModel, NonCanonicalModelAdmin)
