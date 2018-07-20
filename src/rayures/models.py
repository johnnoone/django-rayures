import logging
import stripe
import traceback
from . import fields
from .objs import Price  # noqa
from .utils import price_from_stripe, dt_from_stripe, price_to_stripe, dt_to_stripe
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.db.models.base import ModelBase
from django.db.models.functions import Coalesce, Now
from copy import deepcopy
from datetime import datetime

logger = logging.getLogger('rayures')
PERSISTED_MODELS = {}
STRIPE_OBJECTS = {}


def state_factory(instance):
    if isinstance(instance, dict):
        assert 'object' in instance
        assert 'id' in instance
        data = instance
        version = stripe.api_version
    elif isinstance(instance, (Entity, PersistedModel)):
        data = instance.data
        version = getattr(instance, 'api_version', None)
    else:
        raise ValueError('will not work man')
    return stripe.convert_to_stripe_object(data,
                                           api_key=stripe.api_key,
                                           stripe_account=None,
                                           stripe_version=version)


class SoftDeletionQuerySet(models.QuerySet):
    # TODO: add an attribute "persisted: True everytime a row is instantiated"

    def delete(self):
        return super().update(deleted_at=Coalesce(models.F('deleted_at'), Now()))

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted_at=None)

    def dead(self):
        return self.exclude(deleted_at=None)


class StripeMeta(type):
    def __new__(metacls, name, bases, namespace, object=None):
        global STRIPE_OBJECTS
        cls = super().__new__(metacls, name, bases, namespace)
        if object:
            STRIPE_OBJECTS[object] = cls
            cls._stripe_object = object
        return cls


class PersistedMeta(ModelBase):
    def __new__(metacls, name, bases, namespace, object=None):
        global PERSISTED_MODELS
        cls = super().__new__(metacls, name, bases, namespace)
        if object:
            STRIPE_OBJECTS[object] = cls
            PERSISTED_MODELS[object] = cls
            cls._stripe_object = object
        return cls


class PersistedModel(models.Model, metaclass=PersistedMeta):
    id = models.CharField(max_length=255, primary_key=True, editable=False)
    api_version = models.CharField(max_length=12, editable=False)
    data = JSONField(default=dict)

    deleted_at = models.DateTimeField(editable=False, null=True)
    objects = SoftDeletionQuerySet.as_manager()

    @classmethod
    def from_db(cls, db, field_names, values):
        # Append persisted and deleted hints
        instance = super().from_db(db, field_names, values)
        instance.persisted = True
        instance.deleted = False
        return instance

    @property
    def events(self):
        # got events without the mess of GenericRelation('rayures.Event')
        return Event.objects.filter(object_id=self.id)

    def delete(self):
        self.deleted_at = self.deleted_at or Now()
        self.save(update_fields=['deleted_at'])

    def hard_delete(self):
        super().delete()

    def rebound_fields(self):
        for field in self._meta.private_fields:
            if isinstance(field, fields.StripeField):
                field.rebound(self)
            elif hasattr(field, 'rebound_fields'):
                field.rebound(self)
        return self

    def refresh_from_stripe(self):
        """Refresh current object from stripe.
        """
        if self.deleted_at is not None:
            # TODO: warn won't refresh because it's deleted
            return
        state = state_factory(self)
        try:
            state.refresh()
        except stripe.error.InvalidRequestError as err:
            # TODO: mark it deleted now, but should have been done previously
            logger.warn(f"Tried to refresh {self.id} from stripe but seems to not exists: {err}")
            self.delete()
        else:
            self.refresh_from_state(state)

    def refresh_from_state(self, state):
        """Refresh from a stripe state
        """
        assert self.id == state['id']
        if state.get('deleted', False):
            return self.delete()
        assert self.data['object'] == state['object']
        self.data = state
        self.save(update_fields=['data'])
        self.rebound_fields()

    def refresh_related_objects(self, *names, persist=False):
        """Refresh related objects
        """
        fields = [
            f for f in self._meta.get_fields()
            if isinstance(f, fields.ForeignKey)
        ]
        if names:
            fields = [f for f in fields if f.name in names]

        fom = ((f, getattr(f.related_model, '_stripe_object'), f.related_model) for f in fields)
        fom = [(f, o, m) for f, o, m in fom if o is not None]

        results = {}
        for f, o, m in fom:
            stripe_id = getattr(self, f'{f.name}_id', None)
            if stripe_id is None:
                results[f.name] = None
            else:
                state = state_factory({'object': o, 'id': stripe_id})
                state.refresh()
                results[f.name], _ = m.ingest(state, api_version=stripe.api_version, persist=persist)
        return results

    class Meta:
        abstract = True

    def __repr__(self):
        return f'<{type(self)}({self.id})>'

    def __str__(self):
        return str(self.id or '-')


class UpcomingInvoiceBuilder:
    def __init__(self):
        self._arguments = {}
        self._invoice = None

    def add_argument(self, name, value):
        cloned = self.__class__()
        cloned._arguments = deepcopy(self._arguments)
        cloned._invoice = None
        cloned._arguments.setdefault(name, []).append(value)
        return cloned

    def set_argument(self, name, value):
        cloned = self.__class__()
        cloned._arguments = deepcopy(self._arguments)
        cloned._invoice = None
        cloned._arguments[name] = value
        return cloned

    def set_coupon(self, value: 'Coupon'):
        if isinstance(value, Coupon):
            value = value.id
        if value is False:
            value = ''
        return self.set_argument('coupon', value)

    def set_subscription(self, value: 'Subscription'):
        if isinstance(value, Subscription):
            value = value.id
        return self.set_argument('subscription', value)

    def set_subscription_billing_cycle_anchor(self, value: str):
        return self.set_argument('subscription_billing_cycle_anchor', value)

    def add_subscription_item(self, value: 'SubscriptionItem'):
        if isinstance(value, SubscriptionItem):
            buf = {}
            if value.id:
                buf['id'] = value.id
            if getattr(value, 'clear_usage', None) is True:
                buf['clear_usage'] = True
            if getattr(value, 'deleted', None) is True:
                buf['deleted'] = True
            if value.metadata:
                buf['metadata'] = value.metadata
            if value.plan_id:
                buf['plan'] = value.plan_id
            if value.quantity is not None:
                buf['quantity'] = value.quantity
            value = buf
        return self.add_argument('subscription_items', value)

    def set_subscription_prorate(self, value: bool):
        return self.set_argument('subscription_prorate', value)

    def set_subscription_proration_date(self, value: datetime):
        value = dt_to_stripe(value)
        return self.set_argument('subscription_proration_date', value)

    def add_invoice_item(self, value: 'InvoiceItem'):
        if isinstance(value, InvoiceItem):
            buf = {}
            if value.amount:
                amount, currency = price_to_stripe(value.amount)
                buf['amount'] = amount
                buf['currency'] = currency
            if value.description:
                buf['description'] = value.description
            if value.discountable:
                buf['discountable'] = value.discountable
            if value.id:
                buf['invoiceitem'] = value.id
            if value.metadata:
                buf['metadata'] = value.metadata
            value = buf
        return self.add_argument('invoice_items', value)

    def set_subscription_tax_percent(self, value: float):  # from 0 to 100
        return self.set_argument('subscription_tax_percent', value)

    def set_subscription_trial_end(self, value: datetime):
        value = dt_to_stripe(value)
        return self.set_argument('subscription_trial_end', value)

    def set_subscription_trial_from_plan(self, value: bool):
        return self.set_argument('subscription_trial_from_plan', value)

    def set_customer(self, value: 'Customer'):
        if isinstance(value, Customer):
            value = value.id
        return self.set_argument('customer', value)

    def get(self, cached=True):
        if not cached or self._invoice is None:
            state = self._fetch_from_stripe()
            # state = stripe.Invoice.upcoming(**self._arguments)
            self._invoice = UpcomingInvoice(data=state)
        return self._invoice

    def _fetch_from_stripe(self):
        try:
            return stripe.Invoice.upcoming(**self._arguments)
        except stripe.error.InvalidRequestError as error:
            if error.http_status == 404:
                raise UpcomingInvoice.DoesNotExists() from error
            raise error


class Entity(metaclass=StripeMeta):
    def __init__(self, data):
        self.data = data

    @property
    def id(self):
        return self.data['id']

    @property
    def events(self):
        # got events without the mess of GenericRelation('rayures.Event')
        return Event.objects.filter(object_id=self.data['id'])

    def refresh_from_stripe(self):
        """Refresh current object from stripe.
        """
        state = state_factory(self)
        state.refresh()
        self.refresh_from_state(state)

    def refresh_from_state(self, state):
        """Refresh from a stripe state
        """
        assert self.id == state['id']
        self.data = state

    def __repr__(self):
        return f'<{type(self)}({self.id})>'

    def __str__(self):
        return str(self.id or '-')


class Account(PersistedModel, object='account'):
    country = fields.CharField(source='country')
    created_at = fields.DateTimeField(source='created')
    debit_negative_balances = fields.BooleanField(source='debit_negative_balances')
    email = fields.CharField(source='email')
    support_email = fields.CharField(source='support_email')
    support_phone = fields.CharField(source='support_phone')
    type = fields.CharField(source='type')


class Application(PersistedModel, object='application'):
    """Custom object, not documented in Stripe as for 2018-06-19
    """
    name = fields.CharField(source='name')


class IssuerFraudRecord(PersistedModel, object='issuer_fraud_record'):
    """Custom object, not documented in Stripe as for 2018-06-19
    """
    charge = fields.ForeignKey('rayures.Charge', related_name='issuer_fraud_records', source='charge')
    created_at = fields.DateTimeField(source='created')
    post_date = fields.DateTimeField(source='created')
    fraud_type = fields.CharField(source='fraud_type')


class Payout(PersistedModel, object='payout'):
    type = fields.CharField(source='type')
    amount = fields.PriceField(source='amount')
    method = fields.CharField(source='method')
    status = fields.CharField(source='status')
    created_at = fields.DateTimeField(source='created')
    source_type = fields.CharField(source='source_type')
    arrival_date = fields.DateTimeField(source='created')
    failure_code = fields.CharField(source='failure_code')
    failure_message = fields.CharField(source='failure_message')
    balance_transaction = fields.ForeignKey('rayures.BalanceTransaction',
                                            related_name='+',
                                            source='balance_transaction')
    failure_balance_transaction = fields.ForeignKey('rayures.BalanceTransaction',
                                                    related_name='+',
                                                    source='failure_balance_transaction')
    destination = fields.ForeignKey('rayures.BankAccount',
                                    related_name='+',
                                    source='destination')
    metadata = fields.HashField(source='metadata')

    @property
    def failure(self):
        return PayoutFailure(self.failure_code, self.failure_message, self.failure_balance_transaction)


class BankAccount(PersistedModel, object='bank_account'):
    account_holder_name = fields.CharField(source='account_holder_name')
    account_holder_type = fields.CharField(source='account_holder_type')
    bank_name = fields.CharField(source='bank_name')
    currency = fields.CharField(source='currency')
    fingerprint = fields.CharField(source='fingerprint')
    last4 = fields.CharField(source='last4')
    routing_number = fields.CharField(source='routing_number')
    status = fields.CharField(source='status')
    customer = fields.ForeignKey('rayures.Customer', related_name='+', source='customer')
    default_for_currency = fields.BooleanField(source='default_for_currency')
    metadata = fields.HashField(source='metadata')


class BalanceTransaction(PersistedModel, object='balance_transaction'):
    amount = fields.PriceField(source='amount')
    available_on = fields.DateTimeField(source='available_on')
    created_at = fields.DateTimeField(source='created')
    fee = fields.PriceField(source='amount')
    net = fields.PriceField(source='amount')
    source = fields.ForeignKey('rayures.BalanceTransaction', related_name='+', source='source')
    status = fields.CharField(source='status')
    type = fields.CharField(source='type')


class Charge(PersistedModel, object='charge'):
    amount = fields.PriceField(source='amount')
    amount_refunded = fields.PriceField(source='amount_refunded')
    balance_transaction = fields.ForeignKey('rayures.BalanceTransaction',
                                            related_name='charges',
                                            source='balance_transaction')
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
    balance_transaction = fields.ForeignKey('rayures.BalanceTransaction',
                                            related_name='charges',
                                            source='balance_transaction')
    metadata = fields.HashField(source='metadata')


class Card(PersistedModel, object='card'):
    name = fields.CharField(source='name')
    brand = fields.CharField(source='brand')
    last4 = fields.CharField(source='last4')
    # customer_id = fields.CharField(source='customer')
    customer = fields.ForeignKey('rayures.Customer', related_name='+', source='customer')
    exp_year = fields.IntegerField(source='exp_year')
    exp_month = fields.IntegerField(source='exp_month')
    fingerprint = fields.CharField(source='fingerprint')
    funding = fields.CharField(source='funding')
    available_payout_methods = fields.CharField(source='available_payout_methods')
    cvc_check = fields.CharField(source='cvc_check')
    metadata = fields.HashField(source='metadata')


class Coupon(PersistedModel, object='coupon'):
    amount_off = fields.PriceField(source='amount_off')
    percent_off = fields.IntegerField(source='percent_off')
    created_at = fields.DateTimeField(source='created')
    valid = fields.BooleanField(source='valid')
    duration = fields.CharField(source='duration')
    name = fields.CharField(source='name')
    redeem_by = fields.DateTimeField(source='redeem_by')
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')


class Invoice(PersistedModel, object='invoice'):
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
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')

    @property
    def discount(self):
        if self.data['discount']:
            return Discount(self.data['discount'])


class UpcomingInvoice:
    DoesNotExists = type('DoesNotExists', (ObjectDoesNotExist,), {})
    builder = UpcomingInvoiceBuilder()

    def __init__(self, data):
        self.data = data

    @property
    def customer_id(self):
        return self.data['customer']

    @property
    def customer(self):
        if self.customer_id:
            return Customer.objects.get(id=self.customer_id)

    @property
    def starting_balance(self):
        if self.data['starting_balance'] is not None:
            return price_from_stripe(self.data['starting_balance'], self.data['currency'])

    @property
    def ending_balance(self):
        if self.data['ending_balance'] is not None:
            return price_from_stripe(self.data['ending_balance'], self.data['currency'])

    @property
    def invoice_pdf(self):
        return self.data['invoice_pdf']

    @property
    def amount_due(self):
        if self.data['amount_due'] is not None:
            return price_from_stripe(self.data['amount_due'], self.data['currency'])

    @property
    def amount_paid(self):
        if self.data['amount_paid'] is not None:
            return price_from_stripe(self.data['amount_paid'], self.data['currency'])

    @property
    def amount_remaining(self):
        if self.data['amount_remaining'] is not None:
            return price_from_stripe(self.data['amount_remaining'], self.data['currency'])

    @property
    def period_start_at(self):
        if self.data['period_start'] is not None:
            return dt_from_stripe(self.data['period_start'])

    @property
    def period_end_at(self):
        if self.data['period_end'] is not None:
            return dt_from_stripe(self.data['period_end'])

    @property
    def date(self):
        if self.data['date'] is not None:
            return dt_from_stripe(self.data['date'])

    @property
    def due_date(self):
        if self.data['due_date'] is not None:
            return dt_from_stripe(self.data['due_date'])

    @property
    def next_payment_attempt(self):
        if self.data['next_payment_attempt'] is not None:
            return dt_from_stripe(self.data['next_payment_attempt'])

    @property
    def paid(self):
        return self.data['paid']

    @property
    def forgiven(self):
        return self.data['forgiven']

    @property
    def attempted(self):
        return self.data['attempted']

    @property
    def closed(self):
        return self.data['closed']

    @property
    def total(self):
        if self.data['total'] is not None:
            return price_from_stripe(self.data['total'], self.data['currency'])

    @property
    def subtotal(self):
        if self.data['subtotal'] is not None:
            return price_from_stripe(self.data['subtotal'], self.data['currency'])

    @property
    def charge_id(self):
        return self.data['charge']

    @property
    def charge(self):
        if self.charge_id:
            return Charge.objects.get(id=self.charge_id)

    @property
    def subscription_id(self):
        return self.data['subscription']

    @property
    def subscription(self):
        if self.subscription_id:
            return Subscription.objects.get(id=self.subscription_id)

    @property
    def hosted_invoice_url(self):
        return self.data['hosted_invoice_url']

    @property
    def number(self):
        return self.data['number']

    @property
    def receipt_number(self):
        return self.data['receipt_number']

    @property
    def livemode(self):
        return self.data['livemode']

    @property
    def metadata(self):
        return self.data['metadata']

    @property
    def lines(self):
        for line in self.data['lines']['data']:
            yield InvoiceLine(line)


class InvoiceLine:
    def __init__(self, data):
        self.data = data

    @property
    def id(self):
        return self.data['id']

    @property
    def amount(self):
        if self.data['amount']:
            return price_from_stripe(self.data['amount'], self.data['currency'])

    @property
    def description(self):
        return self.data['description']

    @property
    def discountable(self):
        return self.data['discountable']

    @property
    def invoice_item_id(self):
        return self.data['invoice_item']

    @property
    def invoice_item(self):
        if self.invoice_item_id:
            return InvoiceItem.objects.get(id=self.invoice_item_id)

    @property
    def livemode(self):
        return self.data['livemode']

    @property
    def metadata(self):
        return self.data['metadata']

    @property
    def period(self):
        values = self.data['period'].items()
        return {key: dt_from_stripe(value) for key, value in values}

    @property
    def plan_id(self):
        if self.data['plan']:
            return self.data['plan']['id']

    @property
    def plan(self):
        if self.data['plan']:
            state = self.data['plan']
            id = state['id']
            return Plan(id=id, data=state)
        if self.plan_id:
            return Plan.objects.get(id=self.plan_id)

    @property
    def proration(self):
        return self.data['proration']

    @property
    def quantity(self):
        return self.data['quantity']

    @property
    def subscription_id(self):
        return self.data['subscription']

    @property
    def subscription(self):
        if self.subscription_id:
            return Subscription.objects.get(id=self.subscription_id)

    @property
    def subscription_item_id(self):
        return self.data.get('subscription_item', None)

    @property
    def subscription_item(self):
        si = self.subscription_item_id
        if si:
            for item in self.subscription.items:
                if item.id == si:
                    return item

    @property
    def type(self):
        return self.data['type']


class InvoiceItem(PersistedModel, object='invoiceitem'):
    date = fields.DateTimeField(source='date')
    amount = fields.PriceField(source='amount')
    plan = fields.ForeignKey('rayures.Plan', related_name='invoice_items', source='plan')
    subscription = fields.ForeignKey('rayures.Subscription', related_name='invoice_items', source='subscription')
    invoice = fields.ForeignKey('rayures.Invoice', related_name='invoice_items', source='invoice')
    customer = fields.ForeignKey('rayures.Customer', related_name='invoice_items', source='customer')
    period_start_at = fields.DateTimeField(source='period.start')
    period_end_at = fields.DateTimeField(source='period.end')
    quantity = fields.IntegerField(source='quantity')
    proration = fields.BooleanField(source='proration')
    discountable = fields.BooleanField(source='discountable')
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')


class Order(PersistedModel, object='order'):
    amount = fields.PriceField(source='amount')
    amount_returned = fields.PriceField(source='amount_returned')
    application_fee = fields.PriceField(source='application_fee')
    email = fields.CharField(source='email')
    charge = fields.ForeignKey('rayures.Charge', related_name='orders', source='charge')
    customer = fields.ForeignKey('rayures.Customer', related_name='orders', source='customer')
    status = fields.CharField(source='status')
    created_at = fields.DateTimeField(source='created')
    updated_at = fields.DateTimeField(source='updated')
    paid_at = fields.DateTimeField(source='status_transitions.paid')
    canceled_at = fields.DateTimeField(source='status_transitions.canceled')
    fulfiled_at = fields.DateTimeField(source='status_transitions.fulfiled')
    returned_at = fields.DateTimeField(source='status_transitions.returned')
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')


class Product(PersistedModel, object='product'):
    name = fields.CharField(source='name')
    description = fields.CharField(source='description')
    url = fields.CharField(source='url')
    type = fields.CharField(source='type')
    caption = fields.CharField(source='caption')
    active = fields.BooleanField(source='active')
    created_at = fields.DateTimeField(source='created')
    updated_at = fields.DateTimeField(source='updated')
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')


class Refund(PersistedModel, object='refund'):
    amount = fields.PriceField(source='amount')
    balance_transaction = fields.ForeignKey('rayures.BalanceTransaction',
                                            related_name='charges',
                                            source='balance_transaction')
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
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')


# TODO: Token ?

class SKU(PersistedModel, object='sku'):
    price = fields.PriceField(source='price')
    active = fields.BooleanField(source='active')
    created_at = fields.DateTimeField(source='created')
    updated_at = fields.DateTimeField(source='updated')
    product = fields.ForeignKey('rayures.Product', related_name='skus', source='product')
    livemode = fields.BooleanField(source='livemode')
    inventory = fields.HashField(source='inventory')
    attributes = fields.HashField(source='attributes')
    metadata = fields.HashField(source='metadata')


class Source(PersistedModel, object='source'):
    amount = fields.PriceField(source='amount')
    created_at = fields.DateTimeField(source='created')
    type = fields.CharField(source='type')
    usage = fields.CharField(source='usage')
    status = fields.CharField(source='status')
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')
    customer = fields.ForeignKey('rayures.Customer', related_name='+', source='customer')

    @property
    def card(self):
        card = getattr(self.data, 'card', None)
        if card:
            return SourceCard(card)


class SourceCard:
    def __init__(self, data):
        self.data = data

    @property
    def brand(self):
        return self.data['brand']

    @property
    def last4(self):
        return self.data['last4']

    @property
    def exp_year(self):
        return self.data['exp_year']

    @property
    def exp_month(self):
        return self.data['exp_month']

    @property
    def fingerprint(self):
        return self.data['fingerprint']

    @property
    def cvc_check(self):
        return self.data['cvc_check']


class Transfer(PersistedModel, object='transfer'):
    amount = fields.PriceField(source='amount')
    arrival_date = fields.DateTimeField(source='arrival_date')
    date = fields.DateTimeField(source='date')
    type = fields.CharField(source='type')
    method = fields.CharField(source='method')
    status = fields.CharField(source='status')
    created_at = fields.DateTimeField(source='created')
    balance_transaction_id = fields.CharField(source='balance_transaction')
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')


class Customer(PersistedModel, object='customer'):
    email = fields.CharField(source='email')
    invoice_prefix = fields.CharField(source='invoice_prefix')
    created_at = fields.DateTimeField(source='created')
    account_balance = fields.PriceField(source='account_balance')
    # default_source_id = fields.PriceField(source='default_source')
    # default_source = fields.ForeignKey('rayures.Source', related_name='+', source='default_source')
    delinquent = fields.BooleanField(source='delinquent')
    # discount_id = fields.CharField(source='discount')
    # discount = fields.ForeignKey('rayures.Source', related_name='customers', source='discount')
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')

    @property
    def default_source(self):
        """Returns default source.

        Object can be either a Card or a Source.
        """
        # TODO: make it a relation field searchable by source/card id
        if self.data['default_source']:
            source = self.data['default_source']
            if isinstance(source, str):
                for s in self.data['sources']['data']:
                    # check in local data
                    if s['id'] == source:
                        source = s
                        break
                    else:
                        # worst case, must performs a query
                        obj = Source.objects.filter(id=source).first()
                        if not obj:
                            obj = Card.objects.filter(id=source).first()
                        return obj
            else:
                # must be an embedded object
                assert 'id' in source
                assert 'object' in source
            if source:
                from .reconciliation import reconciliate
                return reconciliate(source, persist=False, api_version=self.api_version, source="orm").instance

    @property
    def sources(self):
        from .reconciliation import reconciliate
        sources = []
        for s in self.data['sources']['data']:
            source = reconciliate(s, persist=False, api_version=self.api_version, source="orm").instance
            sources.append(source)
        if self.data['default_source']:
            ds = self.data['default_source']
            if isinstance(ds, dict):
                ds = ds['id']
                sources = sorted(sources, key=lambda x: 0 if x.id == ds else 1)
        return sources

    @property
    def discount(self):
        if self.data['discount']:
            return Discount(self.data['discount'])

    @property
    def upcoming_invoice(self):
        builder = UpcomingInvoiceBuilder()
        return builder.set_customer(self)


class Dispute(PersistedModel, object='dispute'):
    amount = fields.PriceField(source='amount')
    balance_transaction = fields.ForeignKey('rayures.BalanceTransaction',
                                            related_name='disputes',
                                            source='balance_transaction')
    # FIXME: stripe expose a balance_transactions array[]. see how to expose it?
    # charge_id = fields.CharField(source='charge')
    charge = fields.ForeignKey('rayures.Charge', related_name='disputes', source='charge')
    created_at = fields.DateTimeField(source='created')
    reason = fields.CharField(source='reason')
    status = fields.CharField(source='status')
    livemode = fields.BooleanField(source='livemode')
    metadata = fields.HashField(source='metadata')


class Subscription(PersistedModel, object='subscription'):
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
    livemode = fields.BooleanField(source='livemode')
    # TODO: items
    metadata = fields.HashField(source='metadata')

    @property
    def discount(self):
        if self.data['discount']:
            return Discount(self.data['discount'])

    @property
    def items(self):
        # TODO: generic nested items handler
        # TODO: handle has_more ?
        for data in self.data['items']['data']:
            yield SubscriptionItem(data)


class SubscriptionItem(Entity, object='subcription_item'):
    @property
    def created_at(self):
        return dt_from_stripe(self.data['created_at'])

    @property
    def metadata(self):
        return self.data['metadata']

    @property
    def plan_id(self):
        return self.data['plan']['id']

    @property
    def quantity(self):
        return self.data['quantity']

    @property
    def subscription_id(self):
        return self.data['subscription']


class Plan(PersistedModel, object='plan'):
    name = fields.CharField(source='name')
    interval = fields.CharField(source='interval')
    interval_count = fields.IntegerField(source='interval_count')
    trial_period_days = fields.IntegerField(source='trial_period_days')
    created_at = fields.DateTimeField(source='created')
    amount = fields.PriceField(source='amount')
    aggregate_usage = fields.CharField(source='aggregate_usage')
    billing_scheme = fields.CharField(source='billing_scheme')
    usage_type = fields.CharField(source='usage_type')
    livemode = fields.BooleanField(source='livemode')
    product = fields.ForeignKey('rayures.Product', related_name='plans', source='product')
    metadata = fields.HashField(source='metadata')
    active = fields.BooleanField(source='active')
    billing_scheme = fields.CharField(source='billing_scheme')
    # ? tiers
    # ? tiers_mode
    # ? transform_usage
    usage_type = fields.CharField(source='usage_type')

    # statement_descriptor in product
    # name in product


class Event(PersistedModel, object='event'):
    pending_webhooks = fields.IntegerField(source='pending_webhooks')
    type = fields.CharField(source='type')
    request_id = fields.CharField(source='request.id')
    idempotency_key = fields.CharField(source='request.idempotency_key')
    created_at = fields.DateTimeField(source='created')
    api_version = fields.CharField(source='api_version')
    livemode = fields.BooleanField(source='livemode')

    # obj
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_DEFAULT, null=True, default=None)
    object_id = models.CharField(default=None, max_length=50, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')


class Discount(Entity, object="discount"):

    @property
    def end_at(self):
        return dt_from_stripe(self.data['end'])

    @property
    def start_at(self):
        return dt_from_stripe(self.data['start'])

    @property
    def coupon(self):
        if self['coupon']:
            return Coupon.objects.get(id=self['coupon']['id'])

    @property
    def customer(self):
        if self['customer']:
            return Customer.objects.get(id=self['customer']['id'])

    @property
    def subscription(self):
        if self['subscription']:
            return Subscription.objects.get(id=self['subscription']['id'])


class Balance(Entity, object='balance'):
    @property
    def available(self):
        for item in self.data['available']:
            yield BalanceItem(item)

    @property
    def pending(self):
        for item in self.data['pending']:
            yield BalanceItem(item)


class BalanceItem(Entity):
    @property
    def amount(self):
        return price_from_stripe(self.data['amount'], self.data['currency'])

    @property
    def source_types(self):
        return self.data['source_types']


class PayoutFailure:
    def __init__(self, code, message, balance_transaction):
        self.code = code
        self.message = message
        self.balance_transaction = balance_transaction


# TODO: order_return

class OrderReturn(PersistedModel, object='order_return'):
    amount = fields.PriceField(source='amount')
    created_at = fields.DateTimeField(source='created')
    # todo: items
    # description = fields.CharField(source='description')
    # parent = fields.CharField(source='parent')
    # quantity = fields.IntegerField(source='quantity')
    livemode = fields.BooleanField(source='livemode')
    order = fields.ForeignKey('rayures.Order', related_name='order_returns', source='order')
    refund = fields.ForeignKey('rayures.Refund', related_name='order_returns', source='refund')


class Trace:
    def __init__(self, func, subcalls, parent):
        self.data = {
            'func': f'{func.__module__}.{func.__qualname__}',
            'api_calls': subcalls
        }
        self.parent = parent

    def log_error(self, error):
        # most of stripe.StripeError have http_body
        http_body = getattr(error, 'http_body', None) or ''
        lines = traceback.format_exception(type(error), error, error.__traceback__)
        formatted = ''.join(lines)

        return self.parent.errors.create(
            http_body=http_body,
            func=self.data['func'],
            message=str(error),
            traceback=formatted)


class RayureEventProcess(models.Model):
    STATUS_CHOICES = [
        ('received', 'received'),
        ('success', 'success'),
        ('failure', 'failure')
    ]
    event = models.ForeignKey("rayures.Event", related_name='+', on_delete=models.CASCADE)
    status = models.CharField(choices=STATUS_CHOICES, max_length=12, default='received')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(editable=False, null=True)
    traces = JSONField(default=list)

    def log_trace(self, func, subcalls):
        trace = Trace(func, subcalls, self)
        self.traces.append(trace.data)
        return trace

    class Meta:
        verbose_name = 'Rayure event process'
        verbose_name_plural = 'Rayure event processes'


class RayureEventProcessingError(models.Model):
    process = models.ForeignKey("rayures.RayureEventProcess",
                                related_name='errors',
                                on_delete=models.CASCADE)
    func = models.TextField(null=True)
    http_body = models.TextField()
    message = models.TextField()
    traceback = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True)


class RayureMeta(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    content_type = models.ForeignKey(ContentType,
                                     on_delete=models.CASCADE,
                                     limit_choices_to=models.Q(app_label='rayures'))
    content_object = GenericForeignKey('content_type', 'id')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True)

    event = models.ForeignKey('rayures.Event', on_delete=models.DO_NOTHING, null=True)
    idempotency_key = models.TextField(null=True)
    request_id = models.TextField(null=True)
    source = models.TextField(null=True)

    def __str__(self):
        return f'{self.content_type} {self.id}'
