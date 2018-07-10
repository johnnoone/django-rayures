import json
import pytest
from rayures.views import stripe_web_hook
from rayures.utils import sign_request

view = stripe_web_hook


@pytest.fixture
def event():
    return {
        'id': 'evt_1Cf5fqKf0MzeZZE31sipOwzn',
        'object': 'event',
        'api_version': '2016-07-06',
        'created': 1529498674,
        'data': {
            "object": {
                "object": "invoice",
            }
        },
        'livemode': False,
        'pending_webhooks': 0,
        'request': {
            "id": None,
            "idempotency_key": None
        },
        'type': 'invoice.upcoming'
    }


@pytest.fixture
def payload(event):
    return json.dumps(event)


@pytest.fixture
def sig_header(payload, endpoint_secret):
    req, *_ = sign_request(payload, endpoint_secret)
    return req


@pytest.mark.django_db
@pytest.mark.vcr
def test_success(rf, event, payload, sig_header):
    request = rf.post('/wh', data=payload, content_type='application/json', HTTP_STRIPE_SIGNATURE=sig_header)
    response = view(request)
    assert response.status_code == 200


def test_expect_payload(rf, event, payload, sig_header):
    request = rf.post('/wh', HTTP_STRIPE_SIGNATURE=sig_header)
    response = view(request)
    assert response.status_code == 400


def test_expect_post(rf, event):
    request = rf.get('/wh')
    response = view(request)
    assert response.status_code == 405


def test_expect_STRIPE_SIGNATURE(rf, event):
    request = rf.post('/wh')
    response = view(request)
    assert response.status_code == 400


def test_fake_STRIPE_SIGNATURE(rf, event):
    request = rf.post('/wh', HTTP_STRIPE_SIGNATURE='fo')
    response = view(request)
    assert response.status_code == 400
