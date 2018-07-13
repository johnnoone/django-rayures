import factory
from . import models
from datetime import datetime, timedelta


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Customer
        exclude = 'default_source', 'sources',

    id = factory.Faker('md5', raw_output=False)
    delinquent = False
    default_source = None
    sources = []

    data = factory.Dict({
        "object": "customer",
        "id": factory.SelfAttribute('..id'),
        "account_balance": 0,
        "currency": "usd",
        "delinquent": factory.SelfAttribute('..delinquent'),
        "default_source": factory.SelfAttribute('..default_source'),
        "sources": factory.Dict({
            "data": factory.SelfAttribute('...sources'),
        })
    })


class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Subscription
        exclude = 'timestamp_start', 'timestamp_end', 'now',

    id = factory.Faker('md5', raw_output=False)
    customer = factory.SubFactory('rayures.factories.CustomerFactory')
    plan = factory.SubFactory('rayures.factories.PlanFactory')
    status = 'active'

    now = factory.LazyFunction(datetime.utcnow)
    current_period_start_at = factory.LazyAttribute(lambda o: (o.now - timedelta(days=1)))
    current_period_end_at = factory.LazyAttribute(lambda o: (o.now + timedelta(days=29)))

    timestamp_start = factory.LazyAttribute(lambda o: o.current_period_start_at.timestamp())
    timestamp_end = factory.LazyAttribute(lambda o: o.current_period_end_at.timestamp())

    data = factory.Dict({
        "id": factory.SelfAttribute('..id'),
        "object": "subscription",
        "customer": factory.SelfAttribute('..customer.id'),
        "status": factory.SelfAttribute('..status'),
        "plan": factory.Dict({
            "id": factory.SelfAttribute('...plan.id'),
            "object": "plan",
        }),
        "items": factory.Dict({
            "object": "list",
            "data": factory.List([
                factory.Dict({
                    "id": factory.Faker('md5', raw_output=False),
                    "object": "subscription_item",
                    "plan": factory.Dict({
                        "id": factory.SelfAttribute('......plan.id'),
                        "object": "plan",
                    })
                })
            ])
        }),
        "current_period_start": factory.SelfAttribute('..timestamp_start'),
        "current_period_end": factory.SelfAttribute('..timestamp_end'),
    })

    class Params:
        active = factory.Trait(
            status='active'
        )
        past_due = factory.Trait(
            status='past_due'
        )
        unpaid = factory.Trait(
            status='unpaid'
        )
        trialing = factory.Trait(
            status='trialing'
        )


class PlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Plan

    id = factory.Faker('md5', raw_output=False)
    product = factory.SubFactory("rayures.factories.ProductFactory", type="service")
    data = factory.Dict({
        "id": factory.SelfAttribute('..id'),
        "object": "plan",
        "product": factory.SelfAttribute('..product.id'),
    })


class ProductFactory(factory.Factory):
    class Meta:
        model = models.Product

    id = factory.Faker('md5', raw_output=False)
    type = "service"
    data = factory.Dict({
        "object": "product",
        "id": factory.SelfAttribute('..id'),
        "type": factory.SelfAttribute('..type'),
    })


class CardFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Card

    id = factory.Faker('md5', raw_output=False)
    fingerprint = factory.Faker('md5', raw_output=False)
    customer = factory.SubFactory("rayures.factories.CustomerFactory")
    data = factory.Dict({
        "id": factory.SelfAttribute('..id'),
        "name": None,
        "brand": "Visa",
        "last4": "3956",
        "object": "card",
        "country": "US",
        "funding": "credit",
        "customer": factory.SelfAttribute('..customer.id'),
        "exp_year": 2018,
        "metadata": {},
        "cvc_check": "pass",
        "exp_month": 10,
        "fingerprint": factory.SelfAttribute('..fingerprint'),
        "tokenization_method": None
    })


class ChargeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Charge

    id = factory.Faker('md5', raw_output=False)
    customer = factory.SubFactory('rayures.factories.CustomerFactory')
    metadata = factory.LazyFunction(dict)
    data = factory.Dict({
        "id": factory.SelfAttribute('..id'),
        "object": 'charge',
        "currency": 'usd',
        "amount": 666,
        "customer": factory.SelfAttribute('..customer.id'),
        "metadata": factory.SelfAttribute('..metadata'),
    })
