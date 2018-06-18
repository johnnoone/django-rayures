import logging
import stripe
from .exceptions import DispatchException
from .models import Customer, Event
from .events import dispatch
from contextlib import suppress
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from heroes.exceptions import InvalidInputsError


def get_customer(request) -> Customer:
    raise NotImplementedError


def stripe_ephemeral_key(request):
    """Returns ephemeral key
    """
    if request.method != 'POST':
        raise
    customer = get_customer(request)
    api_version = request.data.get('api_version', stripe.api_version)
    try:
        data = stripe.EphemeralKey.create(customer=customer.stripe_id,
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

    if getattr(settings, 'STRIPE_ENDPOINT_SECRET', None) is not None:
        # verify signature
        endpoint_secret = settings.STRIPE_ENDPOINT_SECRET
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
        event, _ = Event.ingest(payload)
        dispatch(event)
    except DispatchException as error:
        logging.exception(error)
        data = {'error': {'name': error.__class__.__name__, 'message': str(error)}}
    else:
        data = {'success': True}
    return JsonResponse(data, status=200)
