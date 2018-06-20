==============
Django rayures
==============

Rayure is a Django app that integrates Stripe_.
It plugs stripe objects into models via webhooks,
and let you make your custom listener.

It also gives some utilitary classes.

Works only with python >= 3.6 and postgresql >= 9.4.


Quick start
-----------


1. Configure your stripe API key into settings::

    # project_dir/settings.py
    STRIPE_API_KEY = "YOUR API KEY"
    STRIPE_ENDPOINT_SECRET = "YOUR ENDPOINT SECRET"
    STRIPE_PUBLISHABLE_KEY = "YOUR PUBLISHABLE KEY"

    STRIPE_CUSTOMER_FINDER = "your.project.CustomerFinder"
    INSTALLED_APPS += ['rayures']


2. Implement your customer finder::

    # your/project.py
    from rayures.integration import BaseCustomerFinder

    class CustomerFinder(BaseCustomerFinder):
        def find(self, request):
            if request.user.is_authenticated:
                return request.user.customer

    # project_dir/settings.py
    STRIPE_CUSTOMER_FINDER = "your.project.CustomerFinder"


3. Add custom routes::

    # project_dir/urls.py

    from django.conf.urls import include
    from django.urls import path

    urlpatterns += [
        path('YOUR_PREFIX', include('rayures.urls'))
    ]


4. In stripe.com dashboard, add the new webhook url::

    http://YOURPROJECT_URL/YOUR_PREFIX/web-hook



Ephemeral keys
--------------

Publishable key is exposed at http://YOURPROJECT_URL/YOUR_PREFIX/config::

    {
      "publishable_key": "YOUR PUBLISHABLE KEY"
    }

Then configure your client to hit http://YOURPROJECT_URL/YOUR_PREFIX/ephemeral-key::

    {
      "key": "GENERATED EPHEMERAL KEY"
    }


Event listeners
---------------


You can implement your logic via hooks into your apps::

    # your_app/stripe_webhooks
    from rayures import listen

    @listen('customer.*')
    def my_hook_1(event, obj):
        pass

    @listen('customer.created')
    def my_hook_2(event, obj):
        pass


Features
--------

* automatted traces on webhook calls (callees & api)::

    {"success": true, "traces": {"callees": [], "subcalls": []}}

* denormalisation of stripe object into django models
* django admin let explore stripe objects
* some django models integration (refresh_from_state...)
* logging (rayures.*)
* priorities on events (100 by default)
* soft deletion::

    Customer.objects.alive()  # current alive customers
    Customer.objects.dead()  # deleted customers
    Customer.objects.all()  # every customers

* instrumentation of calls::

    from rayures.instrumentation import instrument_client
    with instrument_client() as subcalls:
        stripe.Customer.list()
    print(subcalls)


.. _Stripe: https://stripe.com
