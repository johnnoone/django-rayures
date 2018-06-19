import decimal
import hmac
from .objs import Price
from datetime import datetime
from django.utils import timezone
from functools import singledispatch
from hashlib import sha256
from time import time
from typing import Tuple


# currencies those amount=1 means 100 cents
# https://support.stripe.com/questions/which-zero-decimal-currencies-does-stripe-support
ZERO_DECIMAL_CURRENCIES = [
    "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw",
    "mga", "pyg", "rwf", "vuv", "xaf", "xof", "xpf",
]

CURRENCY_SYMBOLS = {
    "aud": "\u0024",
    "cad": "\u0024",
    "chf": "\u0043\u0048\u0046",
    "cny": "\u00a5",
    "eur": "\u20ac",
    "gbp": "\u00a3",
    "jpy": "\u00a5",
    "myr": "\u0052\u004d",
    "sgd": "\u0024",
    "usd": "\u0024",
}


def price_to_dict(price):
    return {
        'amount': price.amount,
        'currency': price.currency
    }


def price_from_stripe(amount, currency) -> Price:
    if (amount, currency) == (0, None):
        return Price(0, 'usd')
    if amount is not None:
        if currency.lower() not in ZERO_DECIMAL_CURRENCIES:
            amount = amount / decimal.Decimal("100")
        return Price(amount, currency)


def price_to_stripe(price: Price) -> Tuple[int, str]:
    amount = price.amount
    currency = price.currency
    if currency.lower() not in ZERO_DECIMAL_CURRENCIES:
        amount = amount * 100
    return int(amount), currency


@singledispatch
def dt_from_stripe(ts):
    return ts


@dt_from_stripe.register(int)
@dt_from_stripe.register(float)
def dt_from_stripe_number(ts):
    tz = timezone.utc
    return datetime.fromtimestamp(int(ts), tz)


@singledispatch
def dt_to_stripe(ts):
    return ts


@dt_to_stripe.register(datetime)
def dt_to_stripe_datetime(ts):
    return int(ts.timestamp())


def charge_now(ts, ref=None):
    ref = ref or timezone.now()
    if dt_from_stripe(ts) > ref:
        return 'now'
    return dt_to_stripe(ts)


def sign_request(payload, secret, timestamp=None):
    timestamp = timestamp or time()
    signed_payload = ("%d.%s" % (timestamp, payload)).encode('utf-8')
    expected_signature = hmac \
        .new(secret.encode('utf-8'), msg=signed_payload, digestmod=sha256) \
        .hexdigest()
    signature = 't=%d,v1=%s' % (timestamp, expected_signature)
    return signature, payload, timestamp
