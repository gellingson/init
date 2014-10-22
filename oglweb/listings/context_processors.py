# context_processors.py
#
# contains django template processors for the listings app
#
# some of these may be incorporated in TEMPLATE_CONTEXT_PROCESSORS,
# which will include them when processing every template

from crispy_forms.helper import FormHelper
from django.template import RequestContext

def basic_context(request):
    is_alpha = request.session.get('ogl_alpha_user', None)
    return { 'ogl_alpha_user': is_alpha }


# crispy_context()
#
# creates helper(s) to facilitate form formatting
#
# done here rather than in each form to a) facilitate consistent styling
# across the app and b) because some forms are generated from code that
# we don't want to modify, notably the allauth package
#
# NOTES:
#
# Right now we have just the one helper, horiz-form-helper, which does
# the form field in horizontal view only (form tags & buttons to be done
# in HTML)
#
def crispy_context(request):
    helper = FormHelper()
    helper.form_tag = False
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-md-2'
    helper.field_class = 'col-md-8'
    return { 'horiz-form-helper': helper }
