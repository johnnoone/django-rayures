import factory
from . import models


class CustomerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Customer

    id = factory.Faker('md5', raw_output=False)
    delinquent = False
    data = factory.Dict({
        "object": "customer",
        "id": factory.SelfAttribute('..id'),
        'account_balance': 0,
        'currency': 'usd',
        'delinquent': factory.SelfAttribute('..delinquent'),
    })


class SubscriptionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Subscription

    id = factory.Faker('md5', raw_output=False)
    customer = factory.SubFactory('rayures.factories.CustomerFactory')
    plan = factory.SubFactory('rayures.factories.PlanFactory')
    data = factory.Dict({
        "id": factory.SelfAttribute('..id'),
        "object": "subscription",
        "customer": factory.SelfAttribute('..customer.id'),
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
                        "id": factory.SelfAttribute('....plan.id'),
                        "object": "plan",
                    })
                })
            ])
        })
    })


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
