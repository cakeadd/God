from django.urls import path

from .views import HealthCheckView,UserMeView,RegisterView

urlpatterns=[
    path('health/',HealthCheckView.as_view(),name='health_check'),
    path('auth/me/',UserMeView.as_view(),name='user-me'),
    path('auth/register/',RegisterView.as_view(),name='user-register'),

]