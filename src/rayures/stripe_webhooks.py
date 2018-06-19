import logging
import stripe
from .events import listen
from .models import StripeObject


@listen('*', position=10)
def persist_obj(event, obj):
    try:
        if isinstance(obj, StripeObject):
            obj.save()
            print(f'persisted', obj)
        else:
            print(f'ephemeral', obj)
    except Exception as error:
        logging.error(f'failed to persist {obj.id}: {error}')


@listen('*', position=100)
def lol(event, obj):
    stripe.Customer.retrieve('cus_foo')
