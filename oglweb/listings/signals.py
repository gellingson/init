
from allauth.account.signals import user_signed_up
from django.dispatch import receiver

@receiver(user_signed_up)
def set_initial_user_names(request, user, sociallogin=None, **kwargs):
    print("waka waka")
    return
