import pytest
from rayures import factories


@pytest.mark.django_db
class TestCustomerFactory:
    def test_default(self):
        instance = factories.CustomerFactory()
        assert instance.id
        assert instance.data["id"] == instance.id
        assert instance.data["delinquent"] is False

    def test_delinquent(self):
        instance = factories.CustomerFactory(delinquent=True)
        assert instance.id
        assert instance.data["id"] == instance.id
        assert instance.data["delinquent"] is True


@pytest.mark.django_db
class TestSubscriptionFactory:
    def test_default(self):
        instance = factories.SubscriptionFactory()
        assert instance.id
        assert instance.data["id"] == instance.id
        assert instance.plan.id == instance.data["items"]["data"][0]["plan"]["id"]


@pytest.mark.django_db
class TestPlanFactory:
    def test_default(self):
        instance = factories.PlanFactory()
        assert instance.id
        assert instance.data["id"] == instance.id


@pytest.mark.django_db
class TestChargeFactory:
    def test_default(self):
        instance = factories.ChargeFactory()
        assert instance.id
        assert instance.data["id"] == instance.id


@pytest.mark.django_db
class TestCardFactory:
    def test_default(self):
        instance = factories.CardFactory()
        assert instance.id
        assert instance.data["id"] == instance.id


@pytest.mark.django_db
class TestProductFactory:
    def test_default(self):
        instance = factories.ProductFactory()
        assert instance.id
        assert instance.data["id"] == instance.id
