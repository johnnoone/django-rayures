==============
Django rayures
==============

Rayure is a Django app that integrates Stripe_.
It allows to consolidate stripe objects into models via webhooks and other helpers,
and let you plug your custom listeners.

It also gives some utilitary classes.

It works on python >= 3.6 and postgresql >= 9.4.


Quick start
-----------


1. Configure your stripe API key into settings::

    # project_dir/settings.py
    STRIPE_API_KEY = "YOUR API KEY"
    STRIPE_ENDPOINT_SECRET = "YOUR ENDPOINT SECRET"
    STRIPE_PUBLISHABLE_KEY = "YOUR PUBLISHABLE KEY"

    INSTALLED_APPS += ['rayures']


2. Add rayures routes::

    # project_dir/urls.py

    from django.conf.urls import include
    from django.urls import path

    urlpatterns += [
        path('YOUR_PREFIX', include('rayures.urls'))
    ]


3. In stripe.com dashboard, add the new webhook url::

    http://YOURPROJECT_URL/YOUR_PREFIX/web-hook


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

* consolidation of stripe object into django models
* django admin let explore stripe objects
* some django models integration (refresh_from_state...)
* logging (rayures.*)
* priorities on events (100 by default)
* soft deletion of models:

    `instance.delete()` is disable. It will populate instead a deleted_at attribute.
    Then in your queryset, you will have to call `queryset.alive()` to retrieve alive
    only instances.

    `queryset.alive()`
    `queryset.dead()`
    `queryset.hard_delete()`

* instrumentation of calls::

    from rayures.instrumentation import instrument_client
    with instrument_client() as subcalls:
        stripe.Customer.list()
    print(subcalls)


* integrates well with factory boy.

    If you are a factory boy user, you can install our bindings::

        pip install rayures[factories]

    And then start to use them in your tests::

        from rayures.factories import CustomerFactory
        customer = CustomerFactory()

* `instance.persisted` and `instance.deleted` db hints


TODO
----

* Allow to define custom types in metadata attributes

.. _Stripe: https://stripe.com
