import logging
from .events import listen
from .models import PersistedModel

logger = logging.getLogger('rayures')


@listen('*', position=10)
def persist_obj(event, obj):
    try:
        if isinstance(obj, PersistedModel):
            obj.save()
            logger.info(f'persisted {obj}', extra={'obj': obj})
        else:
            logger.info(f'ephemeral {obj}', extra={'obj': obj})
    except Exception as error:
        logger.error(f'failed to persist {obj.id}: {error}', extra={'obj': obj})
