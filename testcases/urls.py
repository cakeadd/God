from django.urls import path

from .views import TestCaseListCreateView,TestCaseDetailView


urlpatterns = [
    path(
        'projects/<int:project_id>/testcases/',
        TestCaseListCreateView.as_view(),
        name='testcase-list-create',
    ),
    path(
        'projects/<int:project_id>/testcases/<int:pk>/',
        TestCaseDetailView.as_view(),
        name='testcase-detail',
    ),
]