from django.contrib import admin

from todo.models import Item, User, Tag

# Register your models here.

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    fields = ('completed', 'title', 'desc', 'creation_date', 'due_date', 'priority', 'assigned', 'estimate', 'tags')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    pass
    
@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    pass
