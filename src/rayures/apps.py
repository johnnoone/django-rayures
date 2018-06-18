from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class RayuresConfig(AppConfig):
    name = 'rayures'

    def ready(self):
        # configure stripe agent
        import stripe
        try:
            stripe.api_key = settings.STRIPE_API_KEY
            stripe.api_version = '2018-05-21'  # TODO: make it configurable?
        except AttributeError as error:
            raise ImproperlyConfigured('STRIPE_API_KEY is mandatory') from error

        # load webhook events
        from django.utils.module_loading import autodiscover_modules
        autodiscover_modules('stripe_webhooks')
