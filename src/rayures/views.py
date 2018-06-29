import json
import logging
import stripe
from .exceptions import DispatchException, InvalidInputsError
from .events import dispatch
from .models import Customer
from .reconciliation import reconciliate_event
from contextlib import suppress
from django.apps import apps
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods


logger = logging.getLogger('rayures')


@require_http_methods(["GET"])
def stripe_config(request):
    """Serve configuration
    """
    return JsonResponse({
        'publishable_key': apps.app_configs['rayures'].publishable_key
    })


def stripe_ephemeral_key(request):
    """Returns ephemeral key
    """
    if request.method != 'POST':
        raise
    customer = get_customer(request)
    api_version = request.data.get('api_version', stripe.api_version)
    try:
        data = stripe.EphemeralKey.create(customer=customer.id,
                                          api_version=api_version)
    except stripe.error.InvalidRequestError as error:
        with suppress(KeyError):
            if error.json_body['error']['type'] == 'invalid_request_error':
                raise InvalidInputsError('Invalid request', errors={'api_version': ['unknown']}) from error
        raise  # pragma: no cover
    return JsonResponse({'key': data})


@require_http_methods(["POST"])
def stripe_web_hook(request):
    """Handle stripe webhooks
    """
    if request.method != 'POST':
        return HttpResponse(status=400)

    payload = request.body
    endpoint_secret = apps.app_configs['rayures'].endpoint_secret
    if endpoint_secret:
        # verify signature
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', None)
        if not sig_header:
            return HttpResponse(status=400)
        try:
            state = stripe.Webhook.construct_event(
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
        state = json.loads(payload)
    if state['type'] == 'ping':
        return HttpResponse()

    data = handle_dispatch(state)
    return JsonResponse(data, status=200)


def handle_dispatch(state):
    try:
        event, created = reconciliate_event(state, persist=True)
        if can_handle_dispatch(event, created):
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
    return apps.app_configs['rayures'].customer_loader(request)


def can_handle_dispatch(event, created):
    # TODO: check previous proc statuses
    return True
