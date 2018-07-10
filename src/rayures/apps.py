from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class RayuresConfig(AppConfig):
    name = "rayures"

    def ready(self):
        from rayures import __version__
        import stripe
        for key in ("STRIPE_API_KEY", "STRIPE_ENDPOINT_SECRET", "STRIPE_PUBLISHABLE_KEY"):
            if not hasattr(settings, key):
                raise ImproperlyConfigured(f"{key} is mandatory")

        # configure stripe agent
        self.api_key = stripe.api_key = settings.STRIPE_API_KEY
        self.api_version = stripe.api_version = "2018-05-21"  # TODO: should it be configurable?
        stripe.set_app_info("django-rayures", version=__version__, url="https://lab.errorist.xyz/django/rayures")

        # client configurations
        self.endpoint_secret = getattr(settings, "STRIPE_ENDPOINT_SECRET", None)
        self.publishable_key = getattr(settings, "STRIPE_PUBLISHABLE_KEY", None)

        # Activate signals
        from . import tasks  # noqa

        # load webhook events from any project
        from django.utils.module_loading import autodiscover_modules
        autodiscover_modules('stripe_webhooks')
