import logging
import stripe
import traceback
from .models import registry as models_registry, Balance, Event, Discount, RayureEventProcessingError
from .instrument import instrument_client
from .prio import PrioritySet
from django.contrib.contenttypes.models import ContentType

registry = PrioritySet()


class DispatchException(Exception):
    def __init__(self, message, *, event, exceptions, data):
        self.message = message
        self.event = event
        self.exceptions = exceptions
        self.data = data
        super().__init__(message)

    @property
    def data(self):
        return [(func.__module__ + '.' + func.__qualname__, log_id, str(error))
                for func, log_id, error in self.exceptions]


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
        raise NotImplementedError("Cannot persist", obj, state)
    return Loaded(None)


def dispatch(event: 'Event'):
    name = event.type
    state = event.data['data']['object']
    obj = load(state, api_version=event.api_version).obj
    # TODO: link non persisted obj, like Discount and invoice.upcoming, customer.discount.created
    if state['object'] in models_registry and state.get('id', None):
        cls = models_registry[state['object']]
        event.content_type = ContentType.objects.get_for_model(cls)
        event.object_id = state['id']
        event.save(update_fields=['content_type', 'object_id'])
    errors = []
    callees = []
    with instrument_client() as subcalls:
        for func in registry[name]:
            try:
                callees.append(f'{func.__module__}.{func.__qualname__}')
                func(event, obj)
            except Exception as error:
                logging.exception(error)
                log_id = log_event_exception(error, func, event).id
                errors.append((func, log_id, error))
        if errors:
            raise DispatchException('multiple errors', event=event, exceptions=errors, data={
                'api_call': subcalls, 'callees': callees
            })
    return {'api_call': subcalls, 'callees': callees}


def log_event_exception(error, func, event):
    if isinstance(error, stripe.StripeError):
        data = error.http_body or ''
    else:
        data = ''
    if isinstance(error, Exception):
        lines = traceback.format_exception(type(error), error, error.__traceback__)
        formatted = ''.join(lines)
    else:
        formatted = ''

    return RayureEventProcessingError.objects.create(
        event=event,
        data=data,
        func=func.__module__ + '.' + func.__qualname__,
        message=str(error),
        traceback=formatted)


def listen(name, *, func=None, position=100):
    """Decorator for dispatcher

    >>> @listen('my.event')
    >>> def func(event, obj):
    >>>     assert event.stripe_type == 'my.event'
    """
    def wrap(func):
        global registry
        # TODO: verify signature
        registry.add(name, func, position)
        return func
    if func:
        return wrap(func)
    return wrap
