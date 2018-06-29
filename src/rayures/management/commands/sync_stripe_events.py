import stripe
from django.core.management.base import BaseCommand
from rayures.reconciliation import reconciliate_event


class Command(BaseCommand):
    help = 'Sync stripe events'

    def handle(self, *args, **options):
        for obj in stripe.Event.all(limit=1000).auto_paging_iter():
            obj, created = reconciliate_event(obj, persist=True)
            status = 'created' if created else 'updated'
            self.stdout.write(f'{type(obj)._stripe_object} {obj.id} {status}')
