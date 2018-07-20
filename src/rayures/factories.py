import factory
from . import models
from .objs import Price
from .utils import price_to_stripe
from datetime import datetime, timedelta


def timestamp(obj):
    if obj is None:
        return
    return int(obj.timestamp())


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Customer
        exclude = 'default_source', 'sources', 'source',

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

    class Params:
        can_pay = factory.Trait(
            delinquent=False,
            source=factory.SubFactory('rayures.factories.CardFactory'),
            default_source=factory.SelfAttribute('source.id'),
            sources=factory.LazyAttribute(lambda o: [o.source.data])
        )


class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Subscription
        exclude = ('timestamp_current_period_start_at',
                   'timestamp_current_period_end_at',
                   'timestamp_start_at',
                   'now',
                   'timestamp_trial_start_at',
                   'timestamp_trial_end_at',
                   'timestamp_canceled_at',
                   'timestamp_ended_at')

    id = factory.Faker('md5', raw_output=False)
    customer = factory.SubFactory('rayures.factories.CustomerFactory')
    plan = factory.SubFactory('rayures.factories.PlanFactory')
    status = 'active'
    canceled_at = None
    ended_at = None

    now = factory.LazyFunction(datetime.utcnow)

    start_at = factory.LazyAttribute(lambda o: (o.now - timedelta(days=40)))
    current_period_start_at = factory.LazyAttribute(lambda o: (o.now - timedelta(days=1)))
    current_period_end_at = factory.LazyAttribute(lambda o: (o.now + timedelta(days=29)))
    trial_start_at = None
    trial_end_at = None

    timestamp_start_at = factory.LazyAttribute(lambda o: timestamp(o.start_at))
    timestamp_canceled_at = factory.LazyAttribute(lambda o: timestamp(o.canceled_at))
    timestamp_ended_at = factory.LazyAttribute(lambda o: timestamp(o.ended_at))
    timestamp_current_period_start_at = factory.LazyAttribute(lambda o: timestamp(o.current_period_start_at))
    timestamp_current_period_end_at = factory.LazyAttribute(lambda o: timestamp(o.current_period_end_at))

    timestamp_trial_start_at = factory.LazyAttribute(lambda o: timestamp(o.trial_start_at))
    timestamp_trial_end_at = factory.LazyAttribute(lambda o: timestamp(o.trial_end_at))
    cancel_at_period_end = False

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
        "current_period_start": factory.SelfAttribute('..timestamp_current_period_start_at'),
        "current_period_end": factory.SelfAttribute('..timestamp_current_period_end_at'),
        "cancel_at_period_end": factory.SelfAttribute('..cancel_at_period_end'),
        "start": factory.SelfAttribute('..timestamp_start_at'),
        "trial_start": factory.SelfAttribute('..timestamp_trial_start_at'),
        "trial_end": factory.SelfAttribute('..timestamp_trial_end_at'),
        "canceled_at": factory.SelfAttribute('..timestamp_canceled_at'),
        "ended_at": factory.SelfAttribute('..timestamp_ended_at'),
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
            status='trialing',
            start_at=factory.LazyAttribute(lambda o: (o.now - timedelta(days=40))),
            current_period_start_at=factory.LazyAttribute(lambda o: (o.now - timedelta(days=1))),
            current_period_end_at=factory.LazyAttribute(lambda o: (o.now - timedelta(days=6))),
            trial_start_at=factory.LazyAttribute(lambda o: o.current_period_start_at),
            trial_end_at=factory.LazyAttribute(lambda o: o.current_period_end_at),
        )
        canceling = factory.Trait(
            status='active',
            cancel_at_period_end=True
        )
        canceled = factory.Trait(
            status='canceled',
            start_at=factory.LazyAttribute(lambda o: (o.now - timedelta(days=40))),
            current_period_start_at=factory.LazyAttribute(lambda o: (o.now - timedelta(days=31))),
            current_period_end_at=factory.LazyAttribute(lambda o: (o.now - timedelta(days=1))),
            canceled_at=factory.LazyAttribute(lambda o: o.current_period_end_at),
            ended_at=factory.LazyAttribute(lambda o: o.current_period_end_at)
        )


class PlanFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Plan
        exclude = ('amount_value',
                   'amount_currency')

    id = factory.Faker('md5', raw_output=False)
    product = factory.SubFactory("rayures.factories.ProductFactory", type="service")

    amount = Price(100, 'usd')
    amount_currency = factory.LazyAttribute(lambda o: o.amount.currency)
    amount_value = factory.LazyAttribute(lambda o: price_to_stripe(o.amount)[0])

    interval = 'month'
    interval_count = 1

    active = True

    data = factory.Dict({
        "id": factory.SelfAttribute('..id'),
        "object": "plan",
        "product": factory.SelfAttribute('..product.id'),
        "amount": factory.SelfAttribute('..amount_value'),
        "currency": factory.SelfAttribute('..amount_currency'),
        "interval": factory.SelfAttribute('..interval'),
        "interval_count": factory.SelfAttribute('..interval_count'),
        "active": factory.SelfAttribute('..active'),
        "billing_scheme": 'per_unit'
    })


class ProductFactory(factory.Factory):
    class Meta:
        model = models.Product

    id = factory.Faker('md5', raw_output=False)
    type = "service"
    name = factory.Faker('sentence')
    caption = None
    description = None

    data = factory.Dict({
        "object": "product",
        "id": factory.SelfAttribute('..id'),
        "type": factory.SelfAttribute('..type'),
        "active": True,
        "attributes": [],
        "caption": factory.SelfAttribute('..caption'),
        "created": 1521455493,
        "deactivate_on": [],
        "description": factory.SelfAttribute('..description'),
        "images": [],
        "livemode": True,
        "metadata": {},
        "name": factory.SelfAttribute('..name'),
        "package_dimensions": None,
        "shippable": False,
        "updated": 1530793625,
        "url": None
    })

    class Params:
        good = factory.Trait(
            type="good",
            name=factory.Faker('sentence'),
            caption=factory.Faker('sentence'),
            description=factory.Faker('sentence')
        )
        service = factory.Trait(
            type="service",
            name=factory.Faker('sentence'),
            caption=None,
            description=None
        )


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


class InvoiceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Invoice

    id = factory.Faker('md5', raw_output=False)
    customer = factory.SubFactory('rayures.factories.CustomerFactory')
    subscription = factory.SubFactory('rayures.factories.SubscriptionFactory',
                                      customer=factory.SelfAttribute('..customer'))
    metadata = factory.LazyFunction(dict)
    data = factory.Dict({
        "id": factory.SelfAttribute('..id'),
        "object": 'invoice',
        "customer": factory.SelfAttribute('..customer.id'),
        "subscription": factory.SelfAttribute('..subscription.id'),
        "metadata": factory.SelfAttribute('..metadata'),
        "paid": True,
        "closed": True
    })


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Event
        exclude = ('now',
                   'timestamp_created_at',
                   'embedded_object')

    id = factory.Faker('md5', raw_output=False)
    type = 'customer.created'

    now = factory.LazyFunction(datetime.utcnow)

    created_at = factory.LazyAttribute(lambda o: (o.now - timedelta(days=40)))
    timestamp_created_at = factory.LazyAttribute(lambda o: timestamp(o.created_at))
    # embedded_object = factory.SubFactory('rayures.factories.CustomerFactory')
    content_object = factory.SubFactory('rayures.factories.CustomerFactory')
    # object_id = factory.SubFactory('rayures.factories.CustomerFactory')

    data = factory.Dict({
        "id": factory.SelfAttribute('..id'),
        "object": 'event',
        'type': factory.SelfAttribute('..type'),
        'api_version': '2018-05-21',
        "created": factory.SelfAttribute('..timestamp_created_at'),
        "data": factory.Dict({
            "object": factory.SelfAttribute('...content_object.data'),
            # "object": factory.SelfAttribute('...embedded_object.data'),
        }),
    })


class SKUFactory(factory.Factory):
    class Meta:
        model = models.SKU
        exclude = ('price_currency', 'price_value')

    id = factory.Faker('md5', raw_output=False)
    product = factory.SubFactory("rayures.factories.ProductFactory", type="good")

    price = Price(100, 'usd')
    price_currency = factory.LazyAttribute(lambda o: o.price.currency)
    price_value = factory.LazyAttribute(lambda o: price_to_stripe(o.price)[0])

    attributes = factory.LazyFunction(dict)
    data = factory.Dict({
        "id": factory.SelfAttribute('..id'),
        "object": 'sku',
        "image": None,
        "price": factory.SelfAttribute('..price_value'),
        "active": True,
        "created": 1513784110,
        "product": factory.SelfAttribute('..product.id'),
        "updated": 1516982164,
        "currency": factory.SelfAttribute('..price_currency'),
        "livemode": True,
        "metadata": {},
        "inventory": {
            "type": "infinite",
            "value": None,
            "quantity": None
        },
        "attributes": factory.SelfAttribute('..attributes'),
        "package_dimensions": None
    })
