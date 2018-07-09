import pytest
from rayures import factories


@pytest.mark.django_db
def test_customer_factory():
    cus = factories.CustomerFactory()
    assert cus.id
    assert cus.data["id"] == cus.id
    assert cus.data["delinquent"] is False


@pytest.mark.django_db
def test_customer_factory_delinquent():
    cus = factories.CustomerFactory(delinquent=True)
    assert cus.id
    assert cus.data["id"] == cus.id
    assert cus.data["delinquent"] is True
