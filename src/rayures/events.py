import logging
from .exceptions import DispatchException
from .instrumentation import instrument_client
from .models import (
    registry as models_registry, Balance, Event, Discount,
    RayureEventProcess
)
from .prio import PrioritySet
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

logger = logging.getLogger('rayures')
registry = PrioritySet()


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
    raise NotImplementedError("Cannot load", obj, state)


def dispatch(event: 'Event'):
    name = event.type
    state = event.data['data']['object']
    delete = event.type.endswith('.deleted')
    obj = load(state, api_version=event.api_version, delete=delete).obj
    # TODO: link non persisted obj, like Discount and invoice.upcoming, customer.discount.created
    if state['object'] in models_registry and state.get('id', None):
        cls = models_registry[state['object']]
        event.content_type = ContentType.objects.get_for_model(cls)
        event.object_id = state['id']
        event.save(update_fields=['content_type', 'object_id'])
    errors = []
    try:
        process = RayureEventProcess.objects.create(event=event)
        for func in registry[name]:
            with instrument_client() as subcalls:
                trace = process.log_trace(func, subcalls)
                try:
                    func(event, obj)
                except Exception as error:
                    proc_error = trace.log_error(error)
                    msg = (
                        f"failed to handle {proc_error.func} for {event.type}. "
                        f"please see {proc_error.id} for more details"
                    )
                    logger.error(msg, extra={
                        'event': event,
                        'error': error,
                        'event_process': process
                    })
                    errors.append((proc_error, error))
            if errors:
                raise DispatchException(
                    'Failed dispatching due to several errors',
                    process=process,
                    event=event,
                    proc_errors=errors)
    finally:
        process.status = 'failure' if errors else 'success'
        process.ended_at = timezone.now()
        process.save(update_fields=['status', 'ended_at', 'traces'])
    return process


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
