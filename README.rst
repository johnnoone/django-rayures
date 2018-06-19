Integrate Stripe into django
============================


Works only with python 3.6 and postgresql 9.4.

Configure your stripe API key into settings::

    # project_dir/settings.py
    STRIPE_API_KEY = "YOUR API KEY"
    INSTALLED_APPS += ['rayures']


Add custom routes::

    # project_dir/urls.py

    from django.conf.urls import include
    from django.urls import path

    urlpatterns += [
        path('YOUR_PREFIX', include('rayures.urls'))
    ]


In stripe.com, declare your webhook path::

    http://YOURPROJECT_URL/YOUR_PREFIX/web-hook


In your client apps, use the ephemeral key url::

    http://YOURPROJECT_URL/YOUR_PREFIX/ephemeral-key


Implement your logic via hooks into your apps::

    # your_app/stripe_webhooks
    from rayures import listen

    @listen('customer.*')
    def my_hook_1(event, obj):
        pass

    @listen('customer.created')
    def my_hook_2(event, obj):
        pass


Features:

* automatted traces on webhook calls (callees & api)::

    {"success": true, "traces": {"callees": [], "subcalls": []}}

* denormalisation of stripe object into django models
* django admin let explore stripe objects
* some django models integration (refresh_from_state...)
* logging (rayures.*)
* priorities on events (100 by default)
