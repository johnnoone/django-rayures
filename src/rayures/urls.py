from . import views
from django.urls import path

urlpatterns = [
    path('ephemeral-key', views.stripe_ephemeral_key, name='stripe-ephemeral-key'),
    path('web-hook', views.stripe_web_hook, name='stripe-webhook')
]
