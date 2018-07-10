import pytest
from rayures import models
from rayures.factories import CustomerFactory


@pytest.fixture
def stripe_id():
    return "foo"


@pytest.fixture
def stripe_object(stripe_id):
    return CustomerFactory(id=stripe_id)


@pytest.mark.django_db
class TestDelete:

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
