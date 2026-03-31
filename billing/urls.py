from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("plans/", views.plans_view, name="plans"),
    path("subscribe/<str:tier>/", views.subscribe_view, name="subscribe"),
    path("success/", views.success_view, name="success"),
    path("portal/", views.portal_view, name="portal"),
    path("refresh/", views.refresh_entitlement_view, name="refresh"),
]
