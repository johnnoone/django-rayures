from .models import PersistedModel
# from django.db.models.signals import post_init
from django.db.models.signals import post_save, pre_delete


def update_persisted(sender, instance, **kwargs):
    instance.persisted = True
    instance.deleted = False


def delete_persisted(sender, instance, **kwargs):
    instance.persisted = False
    instance.deleted = True


# def init_persisted(sender, instance, **kwargs):
#     instance.persisted = None
#     instance.deleted = instance.deleted_at is not None


for model in PersistedModel.__subclasses__():
    post_save.connect(update_persisted, sender=model)
    pre_delete.connect(delete_persisted, sender=model)
    # post_init.connect(init_persisted, sender=model)
