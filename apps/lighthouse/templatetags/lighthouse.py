from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Return d[key], or an empty list if key is missing."""
    return d.get(key, [])


@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    d = context["request"].GET.copy()
    for k, v in kwargs.items():
        d[k] = v
    for k in [k for k, v in d.items() if v is None]:
        del d[k]
    return d.urlencode()
