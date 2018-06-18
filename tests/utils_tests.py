# pylama:ignore=E501

import pytest
from datetime import datetime
from django.utils import timezone
from rayures import utils


@pytest.mark.parametrize('value, expected', [
    (utils.Price(12, 'usd'), {'amount': 12, 'currency': 'usd'}),
    (utils.Price(12, 'eur'), {'amount': 12, 'currency': 'eur'}),
    (utils.Price(12, 'jpy'), {'amount': 12, 'currency': 'jpy'})
])
def test_price_to_dict(value, expected):
    assert utils.price_to_dict(value) == expected


@pytest.mark.parametrize('amount, currency, expected', [
    (1200, 'usd', utils.Price(12, 'usd')),
    (1200, 'eur', utils.Price(12, 'eur')),
    (1200, 'jpy', utils.Price(1200, 'jpy'))
])
def test_price_from_stripe(amount, currency, expected):
    assert utils.price_from_stripe(amount, currency) == expected


@pytest.mark.parametrize('timestamp, expected', [
    (1507392388, datetime(2017, 10, 7, 16, 6, 28, tzinfo=timezone.utc)),
    (datetime(2017, 10, 7, 16, 6, 28, tzinfo=timezone.utc), datetime(2017, 10, 7, 16, 6, 28, tzinfo=timezone.utc)),
    (None, None),
])
def test_dt_from_stripe(timestamp, expected):
    assert utils.dt_from_stripe(timestamp) == expected


@pytest.mark.parametrize('timestamp, ref, expected', [
    (1007392388, datetime(2017, 10, 7, 16, 6, 28, tzinfo=timezone.utc), 1007392388),
    (2007392388, datetime(2017, 10, 7, 16, 6, 28, tzinfo=timezone.utc), 'now'),
    (datetime(2017, 12, 7, 16, 6, 28, tzinfo=timezone.utc), datetime(2017, 10, 7, 16, 6, 28, tzinfo=timezone.utc), 'now'),
    (datetime(2016, 10, 7, 16, 6, 28, tzinfo=timezone.utc), datetime(2017, 10, 7, 16, 6, 28, tzinfo=timezone.utc), 1475856388)
])
def test_charge_now(timestamp, ref, expected):
    assert utils.charge_now(timestamp, ref) == expected
