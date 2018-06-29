from .models import StripeObject, RayuresMeta, Event
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from .signals import stripe_save, stripe_delete

exclude_models = Event,


def update_meta(sender, instance, **kwargs):
    content_type = ContentType.objects.get_for_model(type(instance))
    meta, created = RayuresMeta.objects.update_or_create(id=instance.id, content_type=content_type, defaults={
        'updated_at': timezone.now()
    })


def delete_meta(sender, instance, **kwargs):
    content_type = ContentType.objects.get_for_model(type(instance))
    meta, created = RayuresMeta.objects.update_or_create(id=instance.id, content_type=content_type, defaults={
        'deleted_at': timezone.now()
    })


for model in StripeObject.__subclasses__():
    if isinstance(model, exclude_models):
        continue
    stripe_save.connect(update_meta, model, dispatch_uid="rayures-meta")
    stripe_delete.connect(delete_meta, model, dispatch_uid="rayures-meta")
