from django.urls import path

from .views import EnvironmentListCreateView,EnvironmentDetailView

urlpatterns = [
    path(
        'projects/<int:project_id>/environments/',
        EnvironmentListCreateView.as_view(),
        name='environment-list-create',
    ),
    path(
        'projects/<int:project_id>/environments/<int:pk>/',
        EnvironmentDetailView.as_view(),
        name='environment-detail',
    ),
]