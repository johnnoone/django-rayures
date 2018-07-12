import stripe
from . import models
from .utils import dt_from_stripe
from collections import namedtuple
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.functions import Now
from django.utils import timezone
from email.utils import parsedate_to_datetime


def squeeze_state(state, *,
                  created=None,
                  deleted=None,
                  now=None,
                  api_version=None,
                  request_id=None,
                  idempotency_key=None) -> dict:
    opts = {
        'data': state,
        'created': created,
        'deleted': deleted,
        'now': now,
        'api_version': api_version,
        'request_id': request_id,
        'idempotency_key': idempotency_key,
        'id': None,
        'object': None,
        'account': None,
    }
    last_response = None
    last_response_date = None

    if isinstance(state, stripe.stripe_object.StripeObject):
        # bingo! best alternative
        last_response = state.last_response
        opts.update({
            'account': state.stripe_account,
            'object': getattr(type(state), "class_name", None),
            'id': state.get('id', None)
        })
        if state.stripe_version:
            opts["api_version"] = state.stripe_version
    elif isinstance(state, stripe.stripe_response.StripeResponse):
        last_response = state

    if last_response:
        opts.update({
            'data': last_response.data,
            'request_id': opts['request_id'] or last_response.request_id,
            'idempotency_key': last_response.idempotency_key,
            'api_version': opts['api_version'] or last_response.headers.get('Stripe-Version', None),
        })
        dt = last_response.headers.get('Date', None)
        if dt:
            opts['now'] = last_response_date = parsedate_to_datetime(dt)

    opts['object'] = opts['data'].get('object', opts['object'])  # no object smells bad
    opts['id'] = opts['data'].get('id', opts['id'])  # no id can be invoice.upcoming

    opts['deleted'] = deleted = opts['data'].get('deleted', deleted) is True
    if not deleted and opts['created'] is None:
        # let's try to find if it's a creation by comparing created attrs with Date header
        if ('created' in opts['data']) and last_response_date:
            dt1 = dt_from_stripe(state['created'])
            opts['created'] = dt1 == last_response_date

    return opts


def squeeze_event(event) -> dict:
    opts = {"source": "webhook"}
    if isinstance(event, dict):
        opts.update({
            "event_id": event.get("id", None)
        })
    if isinstance(event, stripe.Event):
        opts.update({
            "now": event["created"],  # FIXME: make it datetime,
            "api_version": event["api_version"],
            "state": event["data"]["object"],
            "event_id": event.id
        })
        if event["request"] is not None:
            opts.update({
                "request_id": event["request"]["id"],
                "idempotency_key": event["request"]["idempotency_key"],
            })
        event_type = event["type"]
    elif isinstance(event, models.Event):
        opts.update({
            "now": event.created_at,
            "api_version": event.api_version,
            "request_id": event.request_id,
            "idempotency_key": event.idempotency_key,
            "state": event.data["data"]["object"],
            "event_id": event.id
        })
        event_type = event.type
    else:
        raise NotImplementedError("whoot?")

    opts["created"] = event_type.endswith('.created')
    opts["deleted"] = event_type.endswith('.deleted')
    return opts


Reconciliation = namedtuple('Reconciliation', 'instance, persisted')


def reconciliate_by_event(event, *, persist=None) -> Reconciliation:
    opts = squeeze_event(event)
    opts.setdefault("persist", persist)

    # we are good so far
    rec = reconciliate(**opts)

    # TODO: link non persisted obj, like Discount and invoice.upcoming, customer.discount.created
    obj = rec.instance
    cls = type(obj)
    if rec.persisted and cls in models.PersistedModel.__subclasses__():
        event.content_type = ContentType.objects.get_for_model(cls)
        event.object_id = obj.id
        event.save(update_fields=['content_type', 'object_id'])
    return rec


def handle_volative_model(data, object, **opts):
    cls = {'balance': models.Balance, 'discount': models.Discount}.get(object)
    if cls:
        instance = cls(data)
        return Reconciliation(instance, False)
    raise NotImplementedError(f'Tristesse {object}')


def handle_incoming_model(data, object, now, deleted, created, api_version, **opts):
    cls = models.PERSISTED_MODELS.get(object)
    instance = cls(data=data, api_version=api_version)
    if created:  # stripe does not give a delete time, try to stick to almost near
        instance.created_at = now or timezone.now()
    if deleted:  # stripe does not give a delete time, try to stick to almost near
        instance.deleted_at = now or timezone.now()
    instance.rebound_fields()
    # TODO: do we care about meta?
    return Reconciliation(instance, False)


def handle_persistable_model(data, object, id, persist, api_version, now, deleted, created, **opts):
    cls = models.PERSISTED_MODELS.get(object)

    defaults = {
        'api_version': api_version
    }
    # 99.999% of the time, deletion are a total mess
    if not data.get('deleted', None):
        defaults['data'] = data

    def load_instance(stripe_id, defaults, cls, qs, created, deleted, now):
        instance = qs.filter(id=stripe_id).first()
        newborn = not instance
        if instance:
            for k, v in defaults.items():
                setattr(instance, k, v)
        else:
            instance = cls(id=stripe_id, **defaults)
            instance.created_at = now
        if created:  # stripe does not give always a create time, try to stick to almost near
            instance.created_at = getattr(instance, 'created_at', None) or now or timezone.now()
        if deleted:  # stripe does not give a delete time, try to stick to almost near
            instance.deleted_at = getattr(instance, 'deleted_at', None) or now or timezone.now()
        else:
            instance.updated_at = now
        instance.rebound_fields()
        return instance, newborn

    if persist is True:
        with transaction.atomic():
            qs = cls.objects.select_for_update(of=('self',))
            instance, newborn = load_instance(id, defaults, cls, qs, created, deleted, now)
            instance.save()
        return Reconciliation(instance, True)
    else:
        qs = cls.objects
        instance, newborn = load_instance(id, defaults, cls, qs, created, deleted, now)
        # TODO: do we care about meta?
        return Reconciliation(instance, False)


def reconciliate_event(state, *,
                       persist=None,
                       api_version=None,
                       request_id=None,
                       idempotency_key=None) -> Reconciliation:
    opts = squeeze_state(state,
                         api_version=api_version,
                         request_id=request_id,
                         idempotency_key=idempotency_key)
    opts.setdefault('persist', persist)
    opts.setdefault('source', "webhook")

    return handle_persistable_model(**opts)


def reconciliate(state, *,
                 created=None,
                 deleted=None,
                 persist=None,
                 source="sdk",
                 now=None,
                 api_version=None,
                 request_id=None,
                 idempotency_key=None,
                 event_id=None) -> Reconciliation:
    opts = squeeze_state(state,
                         created=created,
                         deleted=deleted,
                         now=now,
                         api_version=api_version,
                         request_id=request_id,
                         idempotency_key=idempotency_key)
    opts.setdefault('persist', persist)
    opts.setdefault('source', source)
    opts.setdefault('event_id', event_id)

    if opts['object'] not in models.PERSISTED_MODELS:
        rec = handle_volative_model(**opts)
    elif opts['id'] is None:
        rec = handle_incoming_model(**opts)
    else:
        rec = handle_persistable_model(**opts)

    # FIXME: handle meta now!
    if rec.persisted and opts['object'] not in ('event',):
        handle_meta(rec.instance, **opts)
    return rec


def handle_meta(instance, *, created, deleted, event_id, request_id, idempotency_key, source, **opts):
    cls = type(instance)
    content_type = ContentType.objects.get_for_model(cls)
    defaults = {
        'event_id': event_id,
        'request_id': request_id,
        'idempotency_key': idempotency_key,
        'source': source
    }
    if created:
        defaults['created_at'] = Now()
        defaults['deleted_at'] = None
    if deleted:
        defaults['deleted_at'] = Now()
    else:
        defaults['updated_at'] = Now()
    meta, created = models.RayureMeta.objects.update_or_create(id=instance.id,
                                                               content_type=content_type,
                                                               defaults=defaults)
    return meta
