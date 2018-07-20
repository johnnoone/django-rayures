import pytest
import stripe
from rayures.models import Customer, state_factory
from rayures.reconciliation import reconciliate, reconciliate_by_event


@pytest.mark.django_db
@pytest.mark.vcr
def test_ingest():
    state = stripe.Customer.create(email='test@example.com')
    instance, created = reconciliate(state, persist=True)
    assert created
    assert instance.id == state['id']
    assert instance.data == state
    assert isinstance(instance, Customer)


@pytest.mark.django_db
@pytest.mark.vcr
def test_event():
    event = state_factory({
        "created": 1326853478,
        "livemode": False,
        "id": "evt_00000000000000",
        "type": "account.external_account.created",
        "object": "event",
        "request": None,
        "pending_webhooks": 1,
        "api_version": "2017-08-15",
        "data": {
            "object": {
                "id": "ba_00000000000000",
                "object": "bank_account",
                "account": "acct_00000000000000",
                "account_holder_name": "Jane Austen",
                "account_holder_type": "individual",
                "bank_name": "STRIPE TEST BANK",
                "country": "US",
                "currency": "usd",
                "default_for_currency": False,
                "fingerprint": "25pF3eun1lNSunni",
                "last4": "6789",
                "metadata": {},
                "routing_number": "110000000",
                "status": "new"
            }
        }
    })
    reconciliate_by_event(event)
