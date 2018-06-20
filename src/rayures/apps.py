from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class RayuresConfig(AppConfig):
    name = "rayures"

    def ready(self):
        from rayures import __version__
        import stripe
        for key in ("STRIPE_API_KEY", "STRIPE_ENDPOINT_SECRET", "STRIPE_PUBLISHABLE_KEY", "STRIPE_CUSTOMER_FINDER"):
            if not hasattr(settings, key):
                raise ImproperlyConfigured(f"{key} is mandatory")

        # configure stripe agent
        self.api_key = stripe.api_key = settings.STRIPE_API_KEY
        self.api_version = stripe.api_version = "2018-05-21"  # TODO: should it be configurable?
        stripe.set_app_info("django-rayures", version=__version__, url="https://lab.errorist.xyz/django/rayures")

        # client configurations
        self.endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
        self.publishable_key = settings.STRIPE_PUBLISHABLE_KEY

        # load user finder
        from django.utils.module_loading import import_string
        cls = import_string(settings.STRIPE_CUSTOMER_FINDER)
        self.customer_loader = cls()

        # Activate signals
        from . import signals  # noqa

        # load webhook events
        from django.utils.module_loading import autodiscover_modules
        autodiscover_modules('stripe_webhooks')
