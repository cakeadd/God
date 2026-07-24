from django.urls import path
from .views import (
    ProjectDetailView,
    ProjectListCreateView,
    ProjectMemberDetailView,
    ProjectMemberListView,
)

urlpatterns = [
    path('projects/',ProjectListCreateView.as_view(),name='project-list-create'),
    path('projects/<int:pk>/', ProjectDetailView.as_view(), name='project-detail'),
    path(
        'projects/<int:project_id>/members/',
        ProjectMemberListView.as_view(),
        name='project-member-list',
    ),
    path(
        'projects/<int:project_id>/members/<int:member_id>/',
        ProjectMemberDetailView.as_view(),
        name='project-member-detail',
    ),


]
