# listing_extras.py
#
# container for filters & custom tags
#
# None of these are in active use as of 9/29/14, except through oldtest.html.
# The custom tags may be a dead end; using template inheritence instead right now.
#
from django import template


register = template.Library()

@register.filter
def cut(value, arg):
    """Removes all values of arg from the given string"""
    return value.replace(arg, '')

@register.filter(is_safe=True)
def lower(value):
        return value.lower()

def navbar(context):
    return {
        "fubar": "barfu"
    }


def short_form(context):
    return {
    }


register.inclusion_tag('listings/navbar.html', takes_context=True)(navbar)
register.inclusion_tag('listings/short_form.html', takes_context=True)(short_form)
