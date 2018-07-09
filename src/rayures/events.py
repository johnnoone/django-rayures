import logging
from .exceptions import DispatchException
from .instrumentation import instrument_client
from .models import RayureEventProcess
from .prio import PrioritySet
from .reconciliation import reconciliate_by_event
from django.utils import timezone

logger = logging.getLogger('rayures')
registry = PrioritySet()


def dispatch(event: 'Event'):
    name = event.type
    reconciliation = reconciliate_by_event(event, persist=True)
    obj = reconciliation.instance
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
