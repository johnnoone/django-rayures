import logging
import stripe
from .exceptions import DispatchException
from .events import dispatch
from .models import Customer, Event
from contextlib import suppress
from django.apps import apps
from django.http import HttpResponse, JsonResponse
from heroes.exceptions import InvalidInputsError


def get_customer(request) -> Customer:
    return apps.app_configs['rayures'].customer_loader(request)


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


def stripe_web_hook(request):
    """Handle stripe webhooks
    """

    if request.method != 'POST':
        raise

    endpoint_secret = apps.app_configs['rayures'].endpoint_secret
    if endpoint_secret is not None:
        # verify signature
        payload = request.body
        sig_header = request.META['HTTP_STRIPE_SIGNATURE']
        try:
            payload = stripe.Webhook.construct_event(
                request.body, sig_header, endpoint_secret)
        except ValueError as error:
            # Invalid payload
            logging.exception('stripe_web_hook ValueError - error: %s' % error)
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError as error:
            # Invalid signature
            logging.exception('stripe_web_hook SignatureVerificationError - error: %s' % error)
            return HttpResponse(status=400)
    else:
        payload = request.data

    if payload['type'] == 'ping':
        return HttpResponse()

    try:
        payload = request.data
        event, created = Event.ingest(payload, persist=True)
        if created:
            data = dispatch(event)
    except DispatchException as error:
        logging.exception(error)
        data = {'error': {'name': error.__class__.__name__, 'message': str(error)}, 'data': error.data}
    else:
        data = {'success': True, 'data': data}
    return JsonResponse(data, status=200)
