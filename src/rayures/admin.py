import json
from .models import Card, Charge, Coupon, Customer, Event, Invoice, InvoiceItem, Order, Plan, Product, SKU, Source, Subscription, Transfer
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

    def get_list_display(self, request):
        list_display = super().get_list_display(request)
        if 'show_events_url' not in list_display:
            list_display = list_display + ('show_events_url',)
        return list_display

    def show_events_url(self, obj):
        url = f'{reverse("admin:rayures_event_changelist")}?q={obj.id}'
        return format_html(f'<a href="{url}">show events</a>')
    show_events_url.allow_tags = True
    show_events_url.short_description = 'Events'


@admin.register(Coupon)
class CouponAdmin(ModelAdmin):
    list_display = 'id', 'amount_off', 'created_at', 'valid', 'duration'
    list_filter = 'valid', 'created_at',
    search_fields = '=id',


@admin.register(Invoice)
class InvoiceAdmin(ModelAdmin):
    list_display = 'id', 'total', 'amount_due', 'amount_paid', 'amount_remaining', 'period_start_at', 'period_end_at', 'date', 'due_date', 'paid', 'forgiven', 'attempted', 'closed', 'total', 'subtotal', 'charge_id', 'customer_id', 'subscription_id', 'webhooks_delivered_at', 'number'
    list_filter = 'paid', 'date', 'due_date', 'forgiven', 'closed'
    search_fields = '=id', '=charge_id', '=customer_id', '=subscription_id'


@admin.register(InvoiceItem)
class InvoiceItemAdmin(ModelAdmin):
    list_display = 'id', 'date', 'amount', 'customer_id', 'plan_id', 'subscription_id', 'invoice_id', 'amount', 'quantity', 'period_start_at', 'period_end_at'
    list_filter = 'date',
    search_fields = '=id', '=plan_id', '=customer_id', '=subscription_id'


@admin.register(Order)
class OrderAdmin(ModelAdmin):
    list_display = 'id', 'amount', 'amount_returned', 'application_fee', 'email', 'charge_id', 'customer_id', 'status', 'created_at', 'updated_at', 'paid_at', 'canceled_at', 'fulfiled_at', 'returned_at'
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


@admin.register(Source)
class SourceAdmin(ModelAdmin):
    list_display = 'id', 'amount', 'created_at', 'type', 'usage', 'status'
    list_filter = 'status', 'type', 'created_at'
    search_fields = '=id',


@admin.register(Transfer)
class TransferAdmin(ModelAdmin):
    list_display = 'id', 'amount', 'arrival_date', 'date', 'type', 'method', 'status', 'created_at', 'balance_transaction_id'
    list_filter = 'type', 'method', 'status'
    search_fields = '=id', '=balance_transaction_id'


@admin.register(Charge)
class ChargeAdmin(ModelAdmin):
    list_display = 'id', 'status', 'invoice_id', 'customer_id', 'paid', 'order_id', 'source_id', 'invoice_id', 'amount', 'amount_refunded', 'balance_transaction_id'
    list_filter = 'paid', 'created_at', 'status',
    search_fields = '=id', '=invoice_id', '=customer_id', '=order_id', '=source_id', '=invoice_id'


@admin.register(Customer)
class CustomerAdmin(ModelAdmin):
    list_display = 'id', 'email', 'delinquent', 'invoice_prefix', 'created_at', 'account_balance'
    list_filter = 'created_at', 'delinquent',
    search_fields = '=id', '=email'


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = 'id', 'start_at', 'created_at', 'ended_at', 'trial_start_at', 'trial_end_at', 'canceled_at', 'current_period_end_at', 'current_period_start_at', 'billing_cycle_anchor', 'status', 'billing', 'customer_id', 'plan_id', 'cancel_at_period_end', 'quantity', 'days_until_due'
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
    list_display = 'id', 'pending_webhooks', 'type', 'request_id', 'idempotency_key', 'created_at', 'object_id'
    list_filter = 'type', 'created_at',
    readonly_fields = 'id', 'api_version', 'type', 'created_at', 'pending_webhooks'
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
