
from allauth.account.signals import user_signed_up
from django.apps import AppConfig

class ListingsConfig(AppConfig):
    name = 'listings'
    verbose_name = 'Carbyr listings'

    def ready(self):
        from listings import signals
        return

