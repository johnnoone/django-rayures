from django.apps import apps
from django.core.management.base import BaseCommand
from rayures.events import dispatch


class Command(BaseCommand):
    help = 'Sync stripe events'

    def handle(self, *args, **options):
        cls = apps.get_model('rayures', 'Event')
        qs = cls.objects.all()
        # qs = qs.filter(type='plan.deleted')
        for event in qs.order_by('created_at'):
            print(event, event.created_at)
            dispatch(event)
