# context_processors.py
#
# contains django template processors for the listings app
#
# some of these may be incorporated in TEMPLATE_CONTEXT_PROCESSORS,
# which will include them when processing every template

from django.template import RequestContext

def basic_context(request):
    is_alpha = request.session.get('ogl_alpha_user', None)
    return { 'ogl_alpha_user': is_alpha }

