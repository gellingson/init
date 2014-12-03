
# WTF, doing this as a ModelForm somehow inherits a validator that ensures
# the username is unique... which is OK for  account adds but is blocking
# any updates of other user fields (heh) since the user being edited
# already exists with the given username. This is brain-dead and I can't
# even figure out where it came from?! Anyway, I'm just going to hand-code
# my form rather than using a ModelForm as it's the fastest path forward

#from django.contrib.auth.models import User
#from django.forms import ModelForm

#class UserForm(ModelForm):
#    class Meta:
#        model = User
#        fields = ['first_name', 'last_name', 'username']
        
from django import forms
from django.contrib.auth.models import User
from listings.models import Profile

class UserForm(forms.Form):
    id = forms.IntegerField(required=False, widget=forms.HiddenInput())  # need this to write validation for username
    first_name = forms.CharField(max_length=30, required=False)
    last_name = forms.CharField(max_length=30, required=False)
    username = forms.CharField(min_length=1, max_length=30)
    newsletter = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.fields['newsletter'].label = 'Subscribe to the Carbyr newsletter... we promise not to sell your email, spam you, or otherwise be evil'

    def clean(self):
        cleaned_data = super(UserForm, self).clean()
        id = cleaned_data.get("id")
        uname = cleaned_data.get("username")
        matches = User.objects.filter(username=uname)
        if matches:
            if id:
                # might be this guy....
                if matches[0].id != id:
                    err = forms.ValidationError(
                        "This username is already in use.",
                        code="duplicate")
                    self.add_error('username', err)
        return cleaned_data


class SignupForm(forms.Form):
    newsletter = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super(SignupForm, self).__init__(*args, **kwargs)
        self.fields['newsletter'].label = 'Subscribe to the Carbyr newsletter... we promise not to sell your email, spam you, or otherwise be evil'

    def signup(self, request, user):
        user.profile = Profile()
        user.profile.id = user.id
        if self.cleaned_data['newsletter']:
            user.profile.newsletter = 'Y'
        else:
            user.profile.newsletter = 'N'
        # the user is saved by something in allauth package,
        # but we must save the profile here. Somehow the IDs work out...
        user.profile.save()
