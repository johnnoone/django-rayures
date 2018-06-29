from django.apps import apps
from django.core.management.base import BaseCommand
from rayures.events import dispatch


class Command(BaseCommand):
    help = 'Sync stripe events'

    def handle(self, *args, **options):
        # TODO: option to select only the one that have only failed or never processed
        cls = apps.get_model('rayures', 'Event')
        qs = cls.objects.all()
        # qs = qs.filter(type__startswith='coupon.')
        for event in qs.order_by('created_at'):
            print(event, event.created_at, event.type)
            dispatch(event)
