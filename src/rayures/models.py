import stripe
import logging
import traceback
from . import fields
from .utils import price_from_stripe, dt_from_stripe
from django.contrib.contenttypes.fields import GenericForeignKey
# from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.db.models.base import ModelBase
from django.utils import timezone

logger = logging.getLogger('rayures')
PERSISTED_MODELS = {}


def state_factory(instance):
    if isinstance(instance, dict):
        assert 'object' in instance
        assert 'id' in instance
        data = instance
        version = stripe.api_version
    elif isinstance(instance, StripeObject):
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
        global PERSISTED_MODELS
        cls = super().__new__(metacls, name, bases, namespace)
        if object:
            PERSISTED_MODELS[object] = cls
            cls._stripe_object = object
        return cls


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


class RayuresMeta(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
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


class SoftDeletionQuerySet(models.QuerySet):
    def delete(self):
        return super().update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted_at=None)

    def dead(self):
        return self.exclude(deleted_at=None)


class StripeObject(models.Model, metaclass=StripeMeta):
    id = models.CharField(max_length=255, primary_key=True, editable=False)
    api_version = models.CharField(max_length=12, editable=False)
    data = JSONField(default=dict)

    deleted_at = models.DateTimeField(editable=False, null=True)
    objects = SoftDeletionQuerySet.as_manager()

    @property
    def events(self):
        # got events without the mess of GenericRelation('rayures.Event')
        return Event.objects.filter(object_id=self.id)

    def delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at'])

    def hard_delete(self):
        super().delete()

    def rebound_fields(self):
        for field in self._meta.private_fields:
            if isinstance(field, fields.StripeField):
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
            state.refesh()
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


class Account(StripeObject, object='account'):
    country = fields.CharField(source='country')
    created_at = fields.DateTimeField(source='created')
    debit_negative_balances = fields.BooleanField(source='debit_negative_balances')
    email = fields.CharField(source='email')
    support_email = fields.CharField(source='support_email')
    support_phone = fields.CharField(source='support_phone')
    type = fields.CharField(source='type')


class Application(StripeObject, object='application'):
    """Custom object, not documented in Stripe as for 2018-06-19
    """
    name = fields.CharField(source='name')


class IssuerFraudRecord(StripeObject, object='issuer_fraud_record'):
    """Custom object, not documented in Stripe as for 2018-06-19
    """
    charge = fields.ForeignKey('rayures.Charge', related_name='issuer_fraud_records', source='charge')
    created_at = fields.DateTimeField(source='created')
    post_date = fields.DateTimeField(source='created')
    fraud_type = fields.CharField(source='fraud_type')


class Payout(StripeObject, object='payout'):
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

    @property
    def failure(self):
        return PayoutFailure(self.failure_code, self.failure_message, self.failure_balance_transaction)


class BankAccount(StripeObject, object='bank_account'):
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
    livemode = fields.BooleanField(source='livemode')


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
    livemode = fields.BooleanField(source='livemode')

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
    livemode = fields.BooleanField(source='livemode')


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
    livemode = fields.BooleanField(source='livemode')


class Product(StripeObject, object='product'):
    name = fields.CharField(source='name')
    url = fields.CharField(source='url')
    type = fields.CharField(source='type')
    caption = fields.CharField(source='caption')
    active = fields.BooleanField(source='active')
    created_at = fields.DateTimeField(source='created')
    updated_at = fields.DateTimeField(source='updated')
    livemode = fields.BooleanField(source='livemode')


class Refund(StripeObject, object='refund'):
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


# TODO: Token ?

class SKU(StripeObject, object='sku'):
    price = fields.PriceField(source='price')
    active = fields.BooleanField(source='active')
    created_at = fields.DateTimeField(source='created')
    updated_at = fields.DateTimeField(source='updated')
    # product_id = fields.CharField(source='product')
    product = fields.ForeignKey('rayures.Product', related_name='skus', source='product')
    livemode = fields.BooleanField(source='livemode')


class Source(StripeObject, object='source'):
    amount = fields.PriceField(source='amount')
    created_at = fields.DateTimeField(source='created')
    type = fields.CharField(source='type')
    usage = fields.CharField(source='usage')
    status = fields.CharField(source='status')
    livemode = fields.BooleanField(source='livemode')


class Transfer(StripeObject, object='transfer'):
    amount = fields.PriceField(source='amount')
    arrival_date = fields.DateTimeField(source='arrival_date')
    date = fields.DateTimeField(source='date')
    type = fields.CharField(source='type')
    method = fields.CharField(source='method')
    status = fields.CharField(source='status')
    created_at = fields.DateTimeField(source='created')
    balance_transaction_id = fields.CharField(source='balance_transaction')
    livemode = fields.BooleanField(source='livemode')


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
    livemode = fields.BooleanField(source='livemode')

    @property
    def discount(self):
        if self.data['discount']:
            return Discount(self.data['discount'])


class Dispute(StripeObject, object='dispute'):
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
    livemode = fields.BooleanField(source='livemode')

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
    livemode = fields.BooleanField(source='livemode')


class Event(StripeObject, object='event'):
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


class PayoutFailure:
    def __init__(self, code, message, balance_transaction):
        self.code = code
        self.message = message
        self.balance_transaction = balance_transaction


# TODO: order_return
