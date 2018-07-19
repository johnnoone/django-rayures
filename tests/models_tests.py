import pytest
from rayures import models
from rayures import factories


@pytest.fixture
def stripe_id():
    return "foo"


@pytest.fixture
def stripe_object(stripe_id):
    return factories.CustomerFactory(id=stripe_id)


@pytest.mark.django_db
class TestDelete:
    def test_is_hashable(self, stripe_object):
        hash(stripe_object)

    def test_soft_delete(self, stripe_id, stripe_object):
        qs = models.Customer.objects.filter(id=stripe_id)
        assert stripe_object.persisted is True
        assert stripe_object.deleted is False
        assert qs.alive().count() == 1
        assert qs.dead().count() == 0

        stripe_object.delete()
        assert stripe_object.deleted_at is not None
        assert stripe_object.persisted is True
        assert stripe_object.deleted is False
        assert qs.alive().count() == 0
        assert qs.dead().count() == 1

    def test_hard_delete(self, stripe_id, stripe_object):
        qs = models.Customer.objects.filter(id=stripe_id)
        assert stripe_object.persisted is True
        assert stripe_object.deleted is False
        assert qs.alive().count() == 1
        assert qs.dead().count() == 0

        stripe_object.hard_delete()
        assert stripe_object.persisted is False
        assert stripe_object.deleted is True
        assert qs.alive().count() == 0
        assert qs.dead().count() == 0

    def test_repeated_delete_keeps_first(self, stripe_id, stripe_object):
        stripe_object.delete()
        dt1 = stripe_object.deleted_at
        stripe_object.delete()
        dt2 = stripe_object.deleted_at
        assert dt1 == dt2


class TestPrice:
    def test_is_hashable(self):
        price = models.Price(123, 'usd')
        hash(price)


@pytest.mark.vcr
@pytest.mark.django_db
class TestUpcoming:
    def test_build(self):
        customer = factories.CustomerFactory(id='cus_BRObI5Us8hKBoq')
        plan = factories.PlanFactory(id='PLAN-1-TEST')
        subscription = factories.SubscriptionFactory(id='sub_BROsof61nYTM7D', plan=plan)

        invoice = models.UpcomingInvoice.builder.set_customer('cus_BRObI5Us8hKBoq').get()

        assert invoice.customer_id == 'cus_BRObI5Us8hKBoq'
        assert invoice.customer == customer

        assert invoice.subscription_id == 'sub_BROsof61nYTM7D'
        assert invoice.subscription == subscription

        assert list(invoice.lines)[0].plan_id == 'PLAN-1-TEST'
        assert list(invoice.lines)[0].plan == plan

        assert list(invoice.lines)[0].subscription_id == 'sub_BROsof61nYTM7D'
        assert list(invoice.lines)[0].subscription == subscription
