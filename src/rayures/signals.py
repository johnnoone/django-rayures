from django.db.models.signals import ModelSignal

stripe_delete = ModelSignal(providing_args=["instance"], use_caching=True)
stripe_save = ModelSignal(providing_args=["instance", "created"], use_caching=True)
