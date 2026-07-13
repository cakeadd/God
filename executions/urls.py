from django.urls import path

from .views import TestCaseExecuteView,TestExecutionListView


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
]
