import json
import logging
import stripe
from .events import dispatch
from .exceptions import DispatchException
from .models import Customer, RayureEventProcess
from .reconciliation import reconciliate_event
from datetime import timedelta
from django.apps import apps
from django.db.models import Q
from django.db.models.functions import Now
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods


logger = logging.getLogger('rayures')


@require_http_methods(["POST"])
def stripe_web_hook(request):
    """Handle stripe webhooks
    """
    if request.method != 'POST':
        return HttpResponse(status=400)

    try:
        response = load_stripe_event(request)
        if isinstance(response, HttpResponse):
            return response
        state = response
    except ValueError as error:
        # Invalid payload
        logger.error('stripe_web_hook ValueError - error: %s' % error)
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as error:
        # Invalid signature
        logger.error('stripe_web_hook SignatureVerificationError - error: %s' % error)
        return HttpResponse(status=400)
    data = handle_dispatch(state)
    if isinstance(data, HttpResponse):
        return data
    return JsonResponse(data, status=200)


def load_stripe_event(request) -> stripe.StripeObject:
    endpoint_secret = apps.app_configs['rayures'].endpoint_secret
    print('endpoint_secret', endpoint_secret)
    if endpoint_secret:
        # verify signature
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', None)
        print('sig_header', sig_header)
        if not sig_header:
            return HttpResponse(status=400)
        try:
            payload = request.body
            print('req', payload)
            return stripe.Webhook.construct_event(
                request.body, sig_header, endpoint_secret)
        except ValueError as error:
            # Invalid payload
            logger.error('stripe_web_hook ValueError - error: %s' % error)
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as error:
            # Invalid signature
            logger.error('stripe_web_hook SignatureVerificationError - error: %s' % error)
            return HttpResponse(status=400)
    else:
        return json.loads(request.body)


def handle_dispatch(state):
    if state['type'] == 'ping':
        return HttpResponse()
    # do we have a running process for this event?
    predicate = Q(
        event_id=state['id'],
        status='received',
        started_at__gte=Now() - timedelta(minutes=15)  # staled event for whatever reason
    )
    process_id = RayureEventProcess.objects \
        .filter(predicate) \
        .values_list('id', flat=True) \
        .first()
    if process_id:
        # discard processing
        return {'id': process_id, 'status': 'running'}
    try:
        event, created = reconciliate_event(state, persist=True)
        process = dispatch(event)
    except DispatchException as error:
        data = {'errors': error.formatted_errors}
        process = error.process
    else:
        data = {}
    data.update({'id': process.id, 'status': process.status, 'traces': process.traces})
    return data


def get_customer(request) -> Customer:
    # use custom loader configured
    return apps.app_configs['rayures'].customer_loader.find(request)
