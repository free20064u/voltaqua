"""Context processors for Django templates."""

from django.conf import settings


def currency_symbol(request):
    """Add local currency symbol to template context."""
    return {
        'currency_symbol': getattr(settings, 'LOCAL_CURRENCY_SYMBOL', '$'),
    }
