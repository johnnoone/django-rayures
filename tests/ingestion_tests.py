import pytest
import stripe
from rayures.models import Customer


@pytest.mark.django_db
@pytest.mark.vcr
def test_ingest():
    state = stripe.Customer.create(email='test@example.com')
    instance, created = Customer.ingest(state, persist=True)
    assert created
    assert instance.id == state['id']
    assert instance.data == state
