import django
import os
import pytest
from django.conf import settings

DEFAULT_SETTINGS = dict(
    INSTALLED_APPS=[
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'rayures',
    ],
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'dev',
            'USER': 'postgres',
            'PASSWORD': '3x4mpl3',
            'HOST': '127.0.0.1',
            'PORT': '5433',
        }
    },
    SITE_ID=1,
    ROOT_URLCONF="rayures.urls",
    SECRET_KEY="notasecret",
    STRIPE_API_KEY=os.getenv("STRIPE_SECRET_KEY", "DUMMY"),
    STRIPE_PUBLISHABLE_KEY=os.getenv("STRIPE_PUBLISHABLE_KEY", "DUMMY"),
    STRIPE_ENDPOINT_SECRET=os.getenv("STRIPE_ENDPOINT_SECRET", "DUMMY"),
    STRIPE_CUSTOMER_FINDER="rayures.integration.BaseCustomerFinder"
)


def pytest_configure():
    settings.configure(**DEFAULT_SETTINGS)
    django.setup()


@pytest.fixture
def vcr_config():
    return {
        "filter_headers": [("authorization", "DUMMY")],
    }
