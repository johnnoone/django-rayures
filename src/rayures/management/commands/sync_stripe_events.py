import stripe
from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sync stripe events'

    def handle(self, *args, **options):
        cls = apps.get_model('rayures', 'Event')
        for obj in stripe.Event.all(limit=1000).auto_paging_iter():
            obj, created = cls.ingest(obj, persist=True)
            status = 'created' if created else 'updated'
            self.stdout.write(f'{type(obj)._stripe_object} {obj.id} {status}')
