from . import views
from django.urls import path

urlpatterns = [
    path('web-hook', views.stripe_web_hook, name='stripe-webhook')
]
