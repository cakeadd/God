from django.urls import path

from .views import (
    TestCaseExecuteView,
    TestExecutionDetailView,
    TestExecutionListView,
    TestRunDetailView,
    TestRunListCreateView,
)


urlpatterns = [
    path(
        'projects/<int:project_id>/testcases/<int:testcase_id>/execute/',
        TestCaseExecuteView.as_view(),
        name='testcase-execute',
    ),
    path(
        'projects/<int:project_id>/executions/',
        TestExecutionListView.as_view(),
        name='test-execution-list',
    ),
    path(
        'projects/<int:project_id>/executions/<int:pk>/',
        TestExecutionDetailView.as_view(),
        name='test-execution-detail',
    ),
    path(
        'projects/<int:project_id>/test-runs/',
        TestRunListCreateView.as_view(),
        name='test-run-list-create',
    ),
    path(
        'projects/<int:project_id>/test-runs/<int:pk>/',
        TestRunDetailView.as_view(),
        name='test-run-detail',
    ),
]
