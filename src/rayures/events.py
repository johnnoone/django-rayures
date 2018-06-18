from .models import registry as models_registry, Balance, Event, Discount
from collections import defaultdict
from weakref import WeakSet

registry = defaultdict(WeakSet)


class DispatchException(Exception):
    def __init__(self, exc, event):
        self.event = event
        super().__init__(exc)


class Loaded:
    def __init__(self, obj, persisted=True):
        self.obj = obj
        self.persisted = persisted


def load(state, **defaults) -> Loaded:
    obj = state['object']
    if obj in models_registry:
        instance, _ = models_registry[obj].ingest(state, **defaults)
        return Loaded(instance)
    elif obj == 'balance':
        instance = Balance(state)
        return Loaded(instance, False)
    elif obj == 'discount':
        instance = Discount(state)
        return Loaded(instance, False)
    else:
        import json
        print(json.dumps(state, indent=2))
        raise NotImplementedError("Cannot persist", obj, state)
    return Loaded(None)


def dispatch(event: 'Event'):
    name = event.type
    state = event.data['data']['object']
    loaded = load(state, api_version=event.api_version)
    obj = loaded.obj
    persisted = loaded.persisted
    # TODO: link non persisted obj, like Discount and invoice.upcoming, customer.discount.created
    if obj and persisted:
        event.content_object = obj
        event.save(update_fields=['content_type', 'object_id'])
    for func in registry[name]:
        try:
            func(event, obj)
        except Exception as error:
            raise DispatchException(error, event) from error


def listen(name, func=None):
    def wrap(func):
        global registry
        # TODO: verify signature
        registry[name].add(func)
        return func
    if func:
        return wrap(func)
    return wrap


@listen('customer.created')
@listen('customer.updated')
def import_customer(event, obj):
    print(' -', event.type, obj, '!!!')
