import pytest
import stripe
from rayures.models import Customer
from rayures.reconciliation import reconciliate


@pytest.mark.django_db
@pytest.mark.vcr
def test_ingest():
    state = stripe.Customer.create(email='test@example.com')
    instance, created = reconciliate(state, persist=True)
    assert created
    assert instance.id == state['id']
    assert instance.data == state
    assert isinstance(instance, Customer)
