from django.urls import path
from .views import ApiEndpointListCreateView,ApiEndpointDetailView

urlpatterns = [
    path(
        'projects/<int:project_id>/endpoints/',
        ApiEndpointListCreateView.as_view(),
        name='api-endpoint-list-create'
    ),
    path(
        'projects/<int:project_id>/endpoints/<int:pk>/',
        ApiEndpointDetailView.as_view(),
        name='api-endpoint-detail'
    )
]