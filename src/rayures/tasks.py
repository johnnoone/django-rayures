from .models import PersistedModel
from django.db.models.signals import post_save, pre_delete


def update_persisted(sender, instance, **kwargs):
    print('update persisted')
    instance.persisted = True


def delete_persisted(sender, instance, **kwargs):
    print('delete persisted')
    instance.persisted = False


for model in PersistedModel.__subclasses__():
    print('m', model)

    post_save.connect(update_persisted, sender=model)
    pre_delete.connect(delete_persisted, sender=model)
