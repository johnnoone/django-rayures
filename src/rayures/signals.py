from .models import StripeObject, RayuresMeta
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_save, pre_delete
from django.utils import timezone


def update_meta(sender, instance, update_fields, **kwargs):
    content_type = ContentType.objects.get_for_model(type(instance))
    meta, created = RayuresMeta.objects.update_or_create(id=instance.id, content_type=content_type, defaults={
        'updated_at': timezone.now()
    })


def delete_meta(sender, instance, update_fields, **kwargs):
    content_type = ContentType.objects.get_for_model(type(instance))
    meta, created = RayuresMeta.objects.update_or_create(id=instance.id, content_type=content_type, defaults={
        'deleted_at': timezone.now()
    })


for model in StripeObject.__subclasses__():
    post_save.connect(update_meta, model, dispatch_uid="my_unique_identifier")
    pre_delete.connect(delete_meta, model, dispatch_uid="my_unique_identifier")
