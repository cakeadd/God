from django.urls import path

from .views import ChangePasswordView,HealthCheckView,UserMeView,RegisterView

urlpatterns=[
    path('health/',HealthCheckView.as_view(),name='health_check'),
    path('auth/me/',UserMeView.as_view(),name='user-me'),
    path('auth/change-password/',ChangePasswordView.as_view(),name='user-change-password'),
    path('auth/register/',RegisterView.as_view(),name='user-register'),

]
