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

    def test_active(self):
        instance = factories.SubscriptionFactory(active=True)
        assert instance.id
        assert instance.status == 'active'

    def test_past_due(self):
        instance = factories.SubscriptionFactory(past_due=True)
        assert instance.id
        assert instance.status == 'past_due'

    def test_unpaid(self):
        instance = factories.SubscriptionFactory(unpaid=True)
        assert instance.id
        assert instance.status == 'unpaid'

    def test_trialing(self):
        instance = factories.SubscriptionFactory(trialing=True)
        assert instance.id
        assert instance.status == 'trialing'

    def test_canceling(self):
        instance = factories.SubscriptionFactory(canceling=True)
        assert instance.id
        assert instance.status == 'active'
        assert instance.cancel_at_period_end is True

    def test_canceled(self):
        instance = factories.SubscriptionFactory(canceled=True)
        assert instance.id
        assert instance.status == 'canceled'


@pytest.mark.django_db
class TestPlanFactory:
    def test_default(self):
        instance = factories.PlanFactory()
        assert instance.id
        assert instance.data["id"] == instance.id
        assert instance.product
        assert instance.product.type == "service"


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

    def test_good(self):
        instance = factories.ProductFactory(good=True)
        assert instance.id
        assert instance.data["type"] == "good"
        assert instance.data["name"]
        assert instance.data["caption"]
        assert instance.data["description"]

    def test_service(self):
        instance = factories.ProductFactory(service=True)
        assert instance.id
        assert instance.data["type"] == "service"
        assert instance.data["name"]
        assert instance.data["caption"] is None
        assert instance.data["description"] is None



@pytest.mark.django_db
class TestSKUFactory:
    def test_default(self):
        instance = factories.SKUFactory()
        assert instance.id
        assert instance.data["id"] == instance.id
        assert instance.product
        assert instance.product.type == "good"


@pytest.mark.django_db
class TestInvoiceFactory:
    def test_default(self):
        instance = factories.InvoiceFactory()
        assert instance.id
        assert instance.data["id"] == instance.id


@pytest.mark.django_db
class TestEventFactory:
    def test_default(self):
        instance = factories.EventFactory()
        assert instance.id
        assert instance.data["id"] == instance.id
        assert instance.object_id
        assert instance.content_type
