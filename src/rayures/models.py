import stripe
import logging
from . import fields
from .utils import price_from_stripe, dt_from_stripe
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.base import ModelBase

registry = {}


def state_factory(instance):
    if isinstance(instance, StripeObject):
        data = instance.data
        version = instance.stripe_api_version
    else:
        raise ValueError('will not work man')
    return stripe.convert_to_stripe_object(data,
                                           api_key=stripe.api_key,
                                           stripe_account=None,
                                           stripe_version=version)


class StripeMeta(ModelBase):
    def __new__(metacls, name, bases, namespace, object=None):
        global registry
        cls = super().__new__(metacls, name, bases, namespace)
        if object:
            registry[object] = cls
            cls._stripe_object = object
        return cls


class StripeObject(models.Model, metaclass=StripeMeta):
    id = models.CharField(max_length=255, primary_key=True)
    api_version = models.CharField(max_length=12)
    data = JSONField(default=dict)
    events = GenericRelation('rayures.Event')

    @classmethod
    def ingest(cls, state, api_version=None, **defaults):
        assert cls._stripe_object == state['object']

        defaults['api_version'] = api_version or stripe.api_version
        defaults['data'] = state
        if 'id' not in state:
            logging.warn("Won't persist because there is no ID. "
                         "It may appends with invoice.upcoming. "
                         "object %s" % dict(state))
            return cls(id=None, **defaults), False
        id = state['id']
        return cls.objects.update_or_create(id=id, defaults=defaults)

    def refresh_from_stripe(self):
        """Refresh current object from stripe.
        """
        state = state_factory(self)
        state.refesh()
        self.refresh_from_state(state)

    def refresh_from_state(self, state):
        """Refresh from a stripe state
        """
        # TODO: ensure state['id'] == self.id before proceeding
        self.data = state
        self.save(update_fields=['data'])

    class Meta:
        abstract = True

    def __repr__(self):
        return f'<{type(self)}({self.id})>'

    def __str__(self):
        return str(self.id or '-')


class BalanceTransaction(StripeObject, object='balance_transaction'):
    amount = fields.PriceField(source='amount')
    available_on = fields.DateTimeField(source='available_on')
    created_at = fields.DateTimeField(source='created')
    fee = fields.PriceField(source='amount')
    net = fields.PriceField(source='amount')
    source = fields.ForeignKey('rayures.BalanceTransaction', related_name='+', source='source')
    status = fields.CharField(source='status')
    type = fields.CharField(source='type')


class Charge(StripeObject, object='charge'):
    amount = fields.PriceField(source='amount')
    amount_refunded = fields.PriceField(source='amount_refunded')
    balance_transaction = fields.ForeignKey('rayures.BalanceTransaction', related_name='charges', source='balance_transaction')
    captured = fields.BooleanField(source='captured')
    created_at = fields.DateTimeField(source='created')
    # customer_id = fields.CharField(source='customer')
    customer = fields.ForeignKey('rayures.Customer', related_name='charges', source='customer')

    status = fields.CharField(source='status')

    # invoice_id = fields.CharField(source='invoice')
    invoice = fields.ForeignKey('rayures.Invoice', related_name='charges', source='invoice')
    paid = fields.BooleanField(source='paid')
    refunded = fields.BooleanField(source='refunded')
    # order_id = fields.CharField(source='order')
    order = fields.ForeignKey('rayures.Order', related_name='charges', source='order')
    # source_id = fields.CharField(source='source.id')
    source = fields.ForeignKey('rayures.Source', related_name='charges', source='source.id')
    balance_transaction_id = fields.CharField(source='balance_transaction')


class Card(StripeObject, object='card'):
    name = fields.CharField(source='name')
    brand = fields.CharField(source='brand')
    last4 = fields.CharField(source='last4')
    # customer_id = fields.CharField(source='customer')
    customer = fields.ForeignKey('rayures.Customer', related_name='cards', source='customer')
    exp_year = fields.IntegerField(source='exp_year')
    exp_month = fields.IntegerField(source='exp_month')
    fingerprint = fields.CharField(source='fingerprint')
    funding = fields.CharField(source='funding')
    available_payout_methods = fields.CharField(source='available_payout_methods')
    cvc_check = fields.CharField(source='cvc_check')


class Coupon(StripeObject, object='coupon'):
    amount_off = fields.PriceField(source='amount_off')
    percent_off = fields.IntegerField(source='percent_off')
    created_at = fields.DateTimeField(source='created')
    valid = fields.BooleanField(source='valid')
    duration = fields.CharField(source='duration')
    name = fields.CharField(source='name')
    redeem_by = fields.DateTimeField(source='redeem_by')


# class Discount:  # Make it an entity
#     pass


class Invoice(StripeObject, object='invoice'):
    total = fields.PriceField(source='total')
    starting_balance = fields.PriceField(source='starting_balance')
    ending_balance = fields.PriceField(source='ending_balance')
    invoice_pdf = fields.CharField(source='invoice_pdf')
    amount_due = fields.PriceField(source='amount_due')
    amount_paid = fields.PriceField(source='amount_paid')
    amount_remaining = fields.PriceField(source='amount_remaining')
    period_start_at = fields.DateTimeField(source='period_start')
    period_end_at = fields.DateTimeField(source='period_end')
    date = fields.DateTimeField(source='date')
    due_date = fields.DateTimeField(source='due_date')
    next_payment_attempt = fields.DateTimeField(source='next_payment_attempt')
    paid = fields.BooleanField(source='paid')
    forgiven = fields.BooleanField(source='forgiven')
    attempted = fields.BooleanField(source='attempted')
    closed = fields.BooleanField(source='closed')
    total = fields.PriceField(source='total')
    subtotal = fields.PriceField(source='subtotal')
    # charge_id = fields.CharField(source='charge')
    charge = fields.ForeignKey('rayures.Charge', related_name='invoices', source='charge')
    # customer_id = fields.CharField(source='customer')
    customer = fields.ForeignKey('rayures.Customer', related_name='invoices', source='customer')
    # subscription_id = fields.CharField(source='subscription')
    subscription = fields.ForeignKey('rayures.Subscription', related_name='invoices', source='subscription')
    webhooks_delivered_at = fields.DateTimeField(source='webhooks_delivered_at')
    hosted_invoice_url = fields.CharField(source='hosted_invoice_url')
    number = fields.CharField(source='number')
    receipt_number = fields.CharField(source='receipt_number')

    @property
    def discount(self):
        if self.data['discount']:
            return Discount(self.data['discount'])


class InvoiceItem(StripeObject, object='invoiceitem'):
    date = fields.DateTimeField(source='date')
    amount = fields.PriceField(source='amount')
    # plan_id = fields.CharField(source='plan')
    plan = fields.ForeignKey('rayures.Plan', related_name='invoice_items', source='plan')
    # subscription_id = fields.CharField(source='subscription')
    subscription = fields.ForeignKey('rayures.Subscription', related_name='invoice_items', source='subscription')
    # invoice_id = fields.CharField(source='invoice')
    invoice = fields.ForeignKey('rayures.Invoice', related_name='invoice_items', source='invoice')
    # customer_id = fields.CharField(source='customer')
    customer = fields.ForeignKey('rayures.Customer', related_name='invoice_items', source='customer')
    period_start_at = fields.DateTimeField(source='period.start')
    period_end_at = fields.DateTimeField(source='period.end')
    quantity = fields.IntegerField(source='quantity')
    proration = fields.BooleanField(source='proration')
    discountable = fields.BooleanField(source='discountable')


class Order(StripeObject, object='order'):
    amount = fields.PriceField(source='amount')
    amount_returned = fields.PriceField(source='amount_returned')
    application_fee = fields.PriceField(source='application_fee')
    email = fields.CharField(source='email')
    # charge_id = fields.CharField(source='charge')
    charge = fields.ForeignKey('rayures.Charge', related_name='orders', source='charge')
    # customer_id = fields.CharField(source='customer')
    customer = fields.ForeignKey('rayures.Customer', related_name='orders', source='customer')
    status = fields.CharField(source='status')
    created_at = fields.DateTimeField(source='created')
    updated_at = fields.DateTimeField(source='updated')
    paid_at = fields.DateTimeField(source='status_transitions.paid')
    canceled_at = fields.DateTimeField(source='status_transitions.canceled')
    fulfiled_at = fields.DateTimeField(source='status_transitions.fulfiled')
    returned_at = fields.DateTimeField(source='status_transitions.returned')


class Product(StripeObject, object='product'):
    name = fields.CharField(source='name')
    url = fields.CharField(source='url')
    type = fields.CharField(source='type')
    caption = fields.CharField(source='caption')
    active = fields.BooleanField(source='active')
    created_at = fields.DateTimeField(source='created')
    updated_at = fields.DateTimeField(source='updated')


class Refund(StripeObject, object='refund'):
    amount = fields.PriceField(source='amount')
    balance_transaction_id = fields.CharField(source='balance_transaction')
    charge = fields.ForeignKey('rayures.Charge', related_name='refunds', source='charge')
    created_at = fields.DateTimeField(source='created')
    reason = fields.CharField(source='reason')
    receipt_number = fields.CharField(source='receipt_number')
    status = fields.CharField(source='status')

    name = fields.CharField(source='name')
    url = fields.CharField(source='url')
    type = fields.CharField(source='type')
    caption = fields.CharField(source='caption')
    active = fields.BooleanField(source='active')
    created_at = fields.DateTimeField(source='created')
    updated_at = fields.DateTimeField(source='updated')


# TODO: Token ?

class SKU(StripeObject, object='sku'):
    price = fields.PriceField(source='price')
    active = fields.BooleanField(source='active')
    created_at = fields.DateTimeField(source='created')
    updated_at = fields.DateTimeField(source='updated')
    # product_id = fields.CharField(source='product')
    product = fields.ForeignKey('rayures.Product', related_name='skus', source='product')


class Source(StripeObject, object='source'):
    amount = fields.PriceField(source='amount')
    created_at = fields.DateTimeField(source='created')
    type = fields.CharField(source='type')
    usage = fields.CharField(source='usage')
    status = fields.CharField(source='status')


class Transfer(StripeObject, object='transfer'):
    amount = fields.PriceField(source='amount')
    arrival_date = fields.DateTimeField(source='arrival_date')
    date = fields.DateTimeField(source='date')
    type = fields.CharField(source='type')
    method = fields.CharField(source='method')
    status = fields.CharField(source='status')
    created_at = fields.DateTimeField(source='created')
    balance_transaction_id = fields.CharField(source='balance_transaction')


class Customer(StripeObject, object='customer'):
    email = fields.CharField(source='email')
    invoice_prefix = fields.CharField(source='invoice_prefix')
    created_at = fields.DateTimeField(source='created')
    account_balance = fields.PriceField(source='account_balance')
    # default_source_id = fields.PriceField(source='default_source')
    default_source = fields.ForeignKey('rayures.Source', related_name='+', source='default_source')
    delinquent = fields.BooleanField(source='delinquent')
    # discount_id = fields.CharField(source='discount')
    # discount = fields.ForeignKey('rayures.Source', related_name='customers', source='discount')

    @property
    def discount(self):
        if self.data['discount']:
            return Discount(self.data['discount'])


class Dispute(StripeObject, object='dispute'):
    amount = fields.PriceField(source='amount')
    balance_transaction = fields.ForeignKey('rayures.BalanceTransaction', related_name='disputes', source='balance_transaction')
    # FIXME: stripe expose a balance_transactions array[]. see how to expose it?
    # charge_id = fields.CharField(source='charge')
    charge = fields.ForeignKey('rayures.Charge', related_name='disputes', source='charge')
    created_at = fields.DateTimeField(source='created')
    reason = fields.CharField(source='reason')
    status = fields.CharField(source='status')


class Subscription(StripeObject, object='subscription'):
    start_at = fields.DateTimeField(source='start')
    created_at = fields.DateTimeField(source='created')
    ended_at = fields.DateTimeField(source='ended_at')
    trial_start_at = fields.DateTimeField(source='trial_start')
    trial_end_at = fields.DateTimeField(source='trial_end')
    canceled_at = fields.DateTimeField(source='canceled_at')
    current_period_end_at = fields.DateTimeField(source='current_period_end')
    current_period_start_at = fields.DateTimeField(source='current_period_start')
    billing_cycle_anchor = fields.DateTimeField(source='billing_cycle_anchor')
    status = fields.CharField(source='status')
    billing = fields.CharField(source='billing')
    # customer_id = fields.CharField(source='customer')
    customer = fields.ForeignKey('rayures.Customer', related_name='subscriptions', source='customer')
    # plan_id = fields.CharField(source='plan.id')
    plan = fields.ForeignKey('rayures.Plan', related_name='subscriptions', source='plan.id')
    cancel_at_period_end = fields.BooleanField(source='cancel_at_period_end')
    # discount_id = fields.CharField(source='discount')
    # discount = fields.ForeignKey('rayures.Discount', related_name='subscriptions', source='discount')
    quantity = fields.IntegerField(source='quantity')
    days_until_due = fields.IntegerField(source='days_until_due')

    @property
    def discount(self):
        if self.data['discount']:
            return Discount(self.data['discount'])


class Plan(StripeObject, object='plan'):
    name = fields.CharField(source='name')
    interval = fields.CharField(source='interval')
    interval_count = fields.IntegerField(source='interval_count')
    trial_period_days = fields.IntegerField(source='trial_period_days')
    created_at = fields.DateTimeField(source='created')
    amount = fields.PriceField(source='amount')
    aggregate_usage = fields.CharField(source='aggregate_usage')
    billing_scheme = fields.CharField(source='billing_scheme')
    usage_type = fields.CharField(source='usage_type')


class Event(StripeObject, object='event'):
    pending_webhooks = fields.IntegerField(source='pending_webhooks')
    type = fields.CharField(source='type')
    request_id = fields.CharField(source='request.id')
    idempotency_key = fields.CharField(source='request.idempotency_key')
    created_at = fields.DateTimeField(source='created')
    api_version = fields.CharField(source='api_version')

    # obj
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.CharField(default=None, max_length=50, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')


class Entity:
    def __init__(self, data):
        self.data = data

class Discount(Entity):

    @property
    def end_at(self):
        return dt_from_stripe(self.data['end'])

    @property
    def start_at(self):
        return dt_from_stripe(self.data['start'])

    @property
    def coupon(self):
        if self['coupon']:
            return Coupon.objecst.get(id=self['coupon']['id'])

    @property
    def customer(self):
        if self['customer']:
            return Customer.objecst.get(id=self['customer']['id'])

    @property
    def subscription(self):
        if self['subscription']:
            return Subscription.objecst.get(id=self['subscription']['id'])


class Balance(Entity):
    @property
    def available(self):
        return BalanceItem(self.data['pending'])

    @property
    def pending(self):
        return BalanceItem(self.data['pending'])


class BalanceItem(Entity):
    @property
    def amount(self):
        return price_from_stripe(self.data['amount'], self.data['currency'])

    @property
    def source_types(self):
        return self.data['source_types']
