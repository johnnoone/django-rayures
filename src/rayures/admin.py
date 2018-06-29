import json
from .models import (Account, Card, Charge, Coupon, Customer, Event, Invoice,
                     InvoiceItem, Order, Plan, Product, SKU, Source, Subscription,
                     Transfer, Refund, BankAccount, Payout, Application, IssuerFraudRecord,
                     RayuresMeta, Dispute, RayureEventProcess, RayureEventProcessingError)
from django.contrib import admin
from django.contrib.postgres.fields import JSONField
from django.forms import widgets
from django.utils.html import format_html
from django.urls import reverse


class PrettyJsonWidget(widgets.Textarea):
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs.setdefault('cols', 80)
        attrs.setdefault('rows', 30)
        super().__init__(attrs)

    def format_value(self, value):
        value = json.loads(value)
        value = json.dumps(value, indent=4)
        return super().format_value(value)


class ModelAdmin(admin.ModelAdmin):
    formfield_overrides = {
        JSONField: {'widget': PrettyJsonWidget}
    }

    def has_add_permission(self, request):
        return False

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if 'deleted_at' not in list_display:
            list_display = list_display + ('deleted_at',)
        if 'show_events_url' not in list_display:
            list_display = list_display + ('show_events_url',)
        return list_display

    def get_list_filter(self, request):
        """
        Return a sequence containing the fields to be displayed as filters in
        the right sidebar of the changelist page.
        """
        list_filter = super().get_list_filter(request)
        for field in self.model._meta.get_fields():
            if field.name in ('status', 'type', 'created_at', 'livemode') and field.name not in list_filter:
                list_filter = list_filter + (field.name,)
        if 'deleted_at' not in list_filter:
            list_filter = list_filter + ('deleted_at',)
        return list_filter

    def show_events_url(self, obj):
        url = f'{reverse("admin:rayures_event_changelist")}?q={obj.id}'
        return format_html(f'<a href="{url}">show events</a>')
    show_events_url.allow_tags = True
    show_events_url.short_description = 'Events'


@admin.register(RayuresMeta)
class RayuresMetaAdmin(admin.ModelAdmin):
    list_display = 'id', 'content_type', 'created_at', 'updated_at', 'deleted_at', 'show_obj_url', 'source'
    search_field = '=id', 'created_at', 'updated_at', 'deleted_at', '=event_id', '=request_id'
    readonly_fields = ('id', 'content_type', 'created_at', 'updated_at',
                       'deleted_at', 'event', 'request_id', 'idempotency_key', 'source',)
    list_filter = 'content_type', 'created_at', 'updated_at', 'deleted_at', 'source'

    def has_add_permission(self, request):
        return False

    def show_obj_url(self, obj):
        if obj.id is not None:
            app_label, model = obj.content_type.app_label, obj.content_type.model
            url = f'{reverse(f"admin:{app_label}_{model}_changelist")}?q={obj.id}'
            return format_html(f'<a href="{url}">show object</a>')
    show_obj_url.allow_tags = True
    show_obj_url.short_description = 'Object'


@admin.register(RayureEventProcess)
class RayureEventProcessAdmin(admin.ModelAdmin):
    list_display = 'id', 'event', 'status', 'started_at', 'ended_at', 'show_event_url'
    search_field = '=id', '=event', '=errors__id', 'status', 'started_at', 'ended_at',
    readonly_fields = 'id', 'event', 'status', 'started_at', 'ended_at',

    def has_add_permission(self, request):
        return False

    def show_event_url(self, obj):
        url = f'{reverse("admin:rayures_event_changelist")}?q={obj.event_id}'
        return format_html(f'<a href="{url}">show event</a>')
    show_event_url.allow_tags = True
    show_event_url.short_description = 'Events'


@admin.register(RayureEventProcessingError)
class RayureEventProcessingErrorAdmin(admin.ModelAdmin):
    list_display = 'id', 'created_at', 'message', 'process', 'func',
    search_field = '=id', '=process', '=process__event',
    readonly_fields = 'id', 'process', 'created_at', 'acknowledged_at', 'func', 'message', 'traceback', 'http_body',

    def has_add_permission(self, request):
        return False


@admin.register(Dispute)
class DisputeAdmin(ModelAdmin):
    list_display = 'id', 'amount', 'balance_transaction', 'charge', 'created_at', 'reason', 'status'
    search_field = '=id', '=balance_transaction', '=charge',
    list_filter = 'status', 'reason', 'created_at',


@admin.register(Refund)
class RefundAdmin(ModelAdmin):
    list_display = 'id', 'receipt_number', 'status', 'balance_transaction', 'charge'
    search_field = '=id', '=balance_transaction', '=charge',


@admin.register(IssuerFraudRecord)
class IssuerFraudRecordAdmin(ModelAdmin):
    list_display = 'id', 'charge', 'created_at', 'post_date', 'fraud_type'
    search_field = '=id', '=charge', 'created_at', 'post_date',
    readonly_fields = 'charge',


@admin.register(Payout)
class PayoutAdmin(ModelAdmin):
    list_display = 'id', 'status', 'type', 'balance_transaction', 'amount', 'created_at', 'destination', 'failure_code'
    list_filter = 'status', 'type', 'created_at',
    search_field = '=id', '=balance_transaction', '=destination'


@admin.register(Account)
class AccountAdmin(ModelAdmin):
    list_display = 'id', 'type', 'support_email', 'support_phone',
    search_fields = '=id',


@admin.register(Application)
class ApplicationAdmin(ModelAdmin):
    list_display = 'id', 'name',
    search_fields = '=id',


@admin.register(BankAccount)
class BankAccountAdmin(ModelAdmin):
    list_display = 'id', 'customer', 'status'
    list_filter = 'status',
    search_fields = '=id',
    readonly_fields = 'customer',


@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    list_display = 'id', 'amount_off', 'created_at', 'valid', 'duration'
    list_filter = 'valid', 'created_at',
    search_fields = '=id',


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = ('id', 'total', 'amount_due', 'amount_paid', 'amount_remaining',
                    'period_start_at', 'period_end_at', 'date', 'due_date', 'paid',
                    'forgiven', 'attempted', 'closed', 'total', 'subtotal',
                    'charge_id', 'customer_id', 'subscription_id',
                    'webhooks_delivered_at', 'number')
    list_filter = 'paid', 'date', 'due_date', 'forgiven', 'closed'
    search_fields = '=id', '=charge_id', '=customer_id', '=subscription_id'
    readonly_fields = 'charge', 'subscription', 'customer',


@admin.register(InvoiceItem)
class InvoiceItemAdmin(ModelAdmin):
    list_display = ('id', 'date', 'amount', 'customer_id', 'plan_id',
                    'subscription_id', 'invoice_id', 'amount', 'quantity',
                    'period_start_at', 'period_end_at')
    list_filter = 'date',
    search_fields = '=id', '=plan_id', '=customer_id', '=subscription_id'
    readonly_fields = 'plan', 'subscription', 'invoice', 'customer',


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = ('id', 'amount', 'amount_returned', 'application_fee', 'email',
                    'charge_id', 'customer_id', 'status', 'created_at', 'updated_at',
                    'paid_at', 'canceled_at', 'fulfiled_at', 'returned_at')
    list_filter = 'status', 'created_at', 'updated_at', 'paid_at', 'canceled_at', 'fulfiled_at', 'returned_at',
    search_fields = '=id', '=charge_id', '=customer_id'


@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = 'id', 'name', 'url', 'type', 'active', 'created_at', 'updated_at'
    list_filter = 'active', 'type', 'created_at', 'updated_at'
    search_fields = '=id',


@admin.register(SKU)
class SKUAdmin(ModelAdmin):
    list_display = 'id', 'price', 'active', 'updated_at', 'created_at', 'product_id'
    list_filter = 'active', 'created_at', 'updated_at'
    search_fields = '=id',


@admin.register(Card)
class CardAdmin(ModelAdmin):
    list_display = 'id', 'name', 'brand', 'customer_id', 'last4', 'exp_year', 'exp_month'
    list_filter = 'brand',
    search_fields = '=id', '=customer_id'
    readonly_fields = 'customer',


@admin.register(Source)
class SourceAdmin(ModelAdmin):
    list_display = 'id', 'amount', 'created_at', 'type', 'usage', 'status'
    list_filter = 'status', 'type', 'created_at'
    search_fields = '=id',


@admin.register(Transfer)
class TransferAdmin(ModelAdmin):
    list_display = ('id', 'amount', 'arrival_date', 'date', 'type', 'method',
                    'status', 'created_at', 'balance_transaction_id')
    list_filter = 'type', 'method', 'status'
    search_fields = '=id', '=balance_transaction_id'


@admin.register(Charge)
class ChargeAdmin(ModelAdmin):
    list_display = ('id', 'status', 'invoice_id', 'customer_id', 'paid', 'order_id',
                    'source_id', 'invoice_id', 'amount', 'amount_refunded',
                    'balance_transaction_id')
    list_filter = 'paid', 'created_at', 'status',
    search_fields = '=id', '=invoice_id', '=customer_id', '=order_id', '=source_id', '=invoice_id'
    readonly_fields = 'customer', 'invoice', 'order', 'source', 'balance_transaction', 'created_at'


@admin.register(Customer)
class CustomerAdmin(ModelAdmin):
    list_display = 'id', 'email', 'delinquent', 'invoice_prefix', 'created_at', 'account_balance'
    list_filter = 'created_at', 'delinquent', 'deleted_at',
    search_fields = '=id', '=email'
    readonly_fields = 'default_source',


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ('id', 'start_at', 'created_at', 'ended_at', 'trial_start_at',
                    'trial_end_at', 'canceled_at', 'current_period_end_at',
                    'current_period_start_at', 'billing_cycle_anchor', 'status',
                    'billing', 'customer_id', 'plan_id', 'cancel_at_period_end',
                    'quantity', 'days_until_due')
    list_filter = 'plan_id', 'status', 'created_at', 'ended_at'
    search_fields = '=id', '=customer_id', '=plan_id'


@admin.register(Plan)
class PlanAdmin(ModelAdmin):
    list_display = 'id', 'name', 'interval', 'interval_count', 'trial_period_days', 'created_at'
    list_filter = 'interval', 'trial_period_days'
    readonly_fields = 'id', 'api_version', 'name', 'interval', 'interval_count', 'trial_period_days', 'created_at'
    search_fields = '=id',


@admin.register(Event)
class EventAdmin(ModelAdmin):
    list_display = 'id', 'type', 'request_id', 'idempotency_key', 'created_at', 'object_id', 'show_obj_url',
    list_filter = 'type', 'created_at',
    readonly_fields = 'id', 'api_version', 'type', 'created_at', 'pending_webhooks', 'content_type', 'object_id',
    search_fields = '=id', '=request_id', '=object_id'

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        list_display = tuple(attr for attr in list_display if attr != 'show_events_url')
        if 'show_obj_url' not in list_display:
            list_display = list_display + ('show_obj_url',)
        return list_display

    def show_obj_url(self, obj):
        if obj.object_id is not None:
            app_label, model = obj.content_type.app_label, obj.content_type.model
            url = f'{reverse(f"admin:{app_label}_{model}_changelist")}?q={obj.object_id}'
            return format_html(f'<a href="{url}">show object</a>')
    show_obj_url.allow_tags = True
    show_obj_url.short_description = 'Object'
