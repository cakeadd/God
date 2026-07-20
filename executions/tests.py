from django.urls import reverse
from unittest.mock import Mock, patch

import requests
from rest_framework import status
from rest_framework.test import APITestCase

from environments.models import Environment
from interfaces.models import ApiEndpoint
from projects.models import Project, ProjectMember
from testcases.models import TestCase as ApiTestCase
from users.models import User
from .models import TestExecution as ApiTestExecution, TestRun as ApiTestRun
from .run_services import execute_test_run


class TestExecutionAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            password='owner123456',
        )
        self.member = User.objects.create_user(
            username='member',
            password='member123456',
        )
        self.viewer = User.objects.create_user(
            username='viewer',
            password='viewer123456',
        )

        self.project = Project.objects.create(
            name='Project A',
            description='Test project',
            owner=self.owner,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMember.Role.MEMBER,
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.viewer,
            role=ProjectMember.Role.VIEWER,
        )

        self.endpoint = ApiEndpoint.objects.create(
            project=self.project,
            name='Product List',
            method=ApiEndpoint.Method.GET,
            path='/api/users/{{user_id}}/',
            headers={
                'Authorization': 'Bearer {{token}}',
                'X-Source': 'endpoint',
            },
            query_params={
                'page': 1,
                'owner_id': '{{user_id}}',
            },
            body={
                'filters': {
                    'owner_id': '{{user_id}}',
                },
            },
            created_by=self.owner,
        )

        self.environment = Environment.objects.create(
            project=self.project,
            name='Test Env',
            base_url='http://test.example.com',
            variables={
                'token': 'test-token',
                'user_id': 18,
            },
        )

        self.test_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Product list success',
            expected_status_code=200,
            headers={'X-Trace': 'case-{{user_id}}'},
            query_params={'size': 10},
            body={'payload': {'user_id': '{{user_id}}'}},
            created_by=self.owner,
        )

        member_login = self.client.post(
            reverse('token-obtain-pair'),
            {
                'username': 'member',
                'password': 'member123456',
            },
            format='json',
        )
        self.member_access = member_login.data['access']

        viewer_login = self.client.post(
            reverse('token-obtain-pair'),
            {
                'username': 'viewer',
                'password': 'viewer123456',
            },
            format='json',
        )
        self.viewer_access = viewer_login.data['access']

        self.other_project = Project.objects.create(
            name='Project B',
            description='Other project',
            owner=self.owner,
        )
        ProjectMember.objects.create(
            project=self.other_project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )

        self.other_endpoint = ApiEndpoint.objects.create(
            project=self.other_project,
            name='Other Endpoint',
            method=ApiEndpoint.Method.GET,
            path='/api/other/',
            created_by=self.owner,
        )

        self.other_test_case = ApiTestCase.objects.create(
            project=self.other_project,
            endpoint=self.other_endpoint,
            name='Other Project Case',
            expected_status_code=200,
            created_by=self.owner,
        )

    def auth_as_viewer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.viewer_access}')

    def auth_as_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.member_access}')

    def get_execute_url(self, project, test_case):
        return reverse(
            'testcase-execute',
            kwargs={
                'project_id': project.id,
                'testcase_id': test_case.id,
            },
        )

    def get_execution_list_url(self, project):
        return reverse(
            'test-execution-list',
            kwargs={
                'project_id': project.id,
            },
        )

    def get_execution_detail_url(self, project, execution):
        return reverse(
            'test-execution-detail',
            kwargs={
                'project_id': project.id,
                'pk': execution.id,
            },
        )

    def get_test_run_list_url(self, project):
        return reverse(
            'test-run-list-create',
            kwargs={'project_id': project.id},
        )

    def get_test_run_detail_url(self, project, test_run):
        return reverse(
            'test-run-detail',
            kwargs={
                'project_id': project.id,
                'pk': test_run.id,
            },
        )

    def get_test_run_report_url(self, project, test_run):
        return reverse(
            'test-run-report',
            kwargs={
                'project_id': project.id,
                'pk': test_run.id,
            },
        )

    @patch('executions.services.requests.request')
    def test_member_can_execute_with_replaced_variables(self, mock_request):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'application/json'}
        mock_response.json.return_value = {'message': 'ok'}
        mock_request.return_value = mock_response

        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, self.test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['project'], self.project.id)
        self.assertEqual(response.data['test_case'], self.test_case.id)
        self.assertEqual(response.data['environment'], self.environment.id)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.PASSED)
        self.assertEqual(response.data['executed_by'], self.member.id)
        self.assertEqual(
            response.data['request_url'],
            'http://test.example.com/api/users/18/',
        )
        self.assertEqual(
            response.data['request_headers']['Authorization'],
            'Bearer ***',
        )
        self.assertEqual(response.data['request_headers']['X-Trace'], 'case-18')
        self.assertEqual(response.data['request_query_params']['owner_id'], 18)
        self.assertEqual(
            response.data['request_body']['filters']['owner_id'],
            18,
        )
        self.assertEqual(
            response.data['request_body']['payload']['user_id'],
            18,
        )

        mock_request.assert_called_once_with(
            method='GET',
            url='http://test.example.com/api/users/18/',
            headers={
                'Authorization': 'Bearer test-token',
                'X-Source': 'endpoint',
                'X-Trace': 'case-18',
            },
            params={'page': 1, 'owner_id': 18, 'size': 10},
            json={
                'filters': {'owner_id': 18},
                'payload': {'user_id': 18},
            },
            timeout=10,
        )

        execution = ApiTestExecution.objects.get(id=response.data['id'])
        self.assertEqual(execution.project, self.project)
        self.assertEqual(execution.test_case, self.test_case)
        self.assertEqual(execution.environment, self.environment)
        self.assertEqual(execution.status, ApiTestExecution.Status.PASSED)
        self.assertEqual(execution.executed_by, self.member)

    @patch('executions.services.requests.request')
    def test_missing_variable_creates_error_without_http_request(self, mock_request):
        self.endpoint.headers = {'Authorization': 'Bearer {{missing_token}}'}
        self.endpoint.save(update_fields=['headers'])
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, self.test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.ERROR)
        self.assertEqual(response.data['error_message'], '环境变量 missing_token 未定义')
        mock_request.assert_not_called()

    @patch('executions.services.requests.request')
    def test_status_code_mismatch_marks_execution_failed(self, mock_request):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.headers = {}
        mock_response.json.return_value = {'detail': 'server error'}
        mock_request.return_value = mock_response
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, self.test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.FAILED)
        self.assertEqual(response.data['response_status_code'], 500)
        self.assertEqual(
            response.data['failure_message'],
            '状态码断言失败：期望 200，实际 500',
        )

    @patch('executions.services.requests.request')
    def test_json_field_assertions_pass(self, mock_request):
        self.test_case.assertions = [
            {
                'type': 'json_field_equals',
                'path': 'data.items.0.id',
                'expected': 18,
            },
            {
                'type': 'json_field_equals',
                'path': 'success',
                'expected': True,
            },
        ]
        self.test_case.save(update_fields=['assertions'])
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            'success': True,
            'data': {'items': [{'id': 18}]},
        }
        mock_request.return_value = mock_response
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, self.test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.PASSED)
        self.assertEqual(response.data['failure_message'], '')

    @patch('executions.services.requests.request')
    def test_json_field_assertions_save_all_failure_reasons(self, mock_request):
        self.test_case.assertions = [
            {
                'type': 'json_field_equals',
                'path': 'data.user.id',
                'expected': 18,
            },
            {
                'type': 'json_field_equals',
                'path': 'data.user.name',
                'expected': 'Alice',
            },
        ]
        self.test_case.save(update_fields=['assertions'])
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {
            'data': {'user': {'id': 19}},
        }
        mock_request.return_value = mock_response
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, self.test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.FAILED)
        self.assertIn(
            'data.user.id 期望 18，实际 19',
            response.data['failure_message'],
        )
        self.assertIn(
            'data.user.name，字段 name 不存在',
            response.data['failure_message'],
        )

    @patch('executions.services.requests.request')
    def test_non_json_response_fails_json_assertion(self, mock_request):
        self.test_case.assertions = [
            {
                'type': 'json_field_equals',
                'path': 'code',
                'expected': 0,
            },
        ]
        self.test_case.save(update_fields=['assertions'])
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'Content-Type': 'text/html'}
        mock_response.json.side_effect = ValueError
        mock_response.text = '<html>error</html>'
        mock_request.return_value = mock_response
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, self.test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.FAILED)
        self.assertEqual(
            response.data['failure_message'],
            'JSON 字段断言失败：响应不是有效 JSON',
        )

    @patch('executions.services.requests.request')
    def test_request_exception_marks_execution_error(self, mock_request):
        mock_request.side_effect = requests.Timeout('request timed out')
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, self.test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.ERROR)
        self.assertIn('request timed out', response.data['error_message'])

    def test_execution_without_environment_marks_error(self):
        endpoint = ApiEndpoint.objects.create(
            project=self.project,
            name='Health Check',
            method=ApiEndpoint.Method.GET,
            path='/api/health/',
            created_by=self.owner,
        )
        test_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=endpoint,
            name='No environment case',
            expected_status_code=200,
            created_by=self.owner,
        )
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.ERROR)
        self.assertEqual(
            response.data['error_message'],
            '测试用例未绑定环境，项目也没有可用的默认环境',
        )

    @patch('executions.services.requests.request')
    def test_execution_without_bound_environment_uses_default(self, mock_request):
        self.environment.is_default = True
        self.environment.save(update_fields=['is_default'])
        test_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            name='Use default environment case',
            expected_status_code=200,
            created_by=self.owner,
        )
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {'message': 'ok'}
        mock_request.return_value = mock_response
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.PASSED)
        self.assertEqual(response.data['environment'], self.environment.id)
        mock_request.assert_called_once()

    @patch('executions.services.requests.request')
    def test_inactive_bound_environment_does_not_use_default(self, mock_request):
        self.environment.is_active = False
        self.environment.save(update_fields=['is_active'])
        default_environment = Environment.objects.create(
            project=self.project,
            name='Fallback Default',
            base_url='http://default.example.com',
            is_default=True,
        )
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, self.test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], ApiTestExecution.Status.ERROR)
        self.assertEqual(response.data['environment'], self.environment.id)
        self.assertEqual(
            response.data['error_message'],
            '测试用例绑定的环境已停用',
        )
        self.assertNotEqual(response.data['environment'], default_environment.id)
        mock_request.assert_not_called()

    def test_viewer_cannot_execute_testcase(self):
        self.auth_as_viewer()

        response = self.client.post(
            self.get_execute_url(self.project, self.test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ApiTestExecution.objects.count(), 0)

    def test_cannot_execute_testcase_from_other_project(self):
        self.auth_as_member()

        response = self.client.post(
            self.get_execute_url(self.project, self.other_test_case),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(ApiTestExecution.objects.count(), 0)

    def test_execution_list_only_returns_current_project_records(self):
        current_execution = ApiTestExecution.objects.create(
            project=self.project,
            test_case=self.test_case,
            environment=self.environment,
            status=ApiTestExecution.Status.PENDING,
            executed_by=self.owner,
        )
        ApiTestExecution.objects.create(
            project=self.other_project,
            test_case=self.other_test_case,
            status=ApiTestExecution.Status.PENDING,
            executed_by=self.owner,
        )

        self.auth_as_member()
        response = self.client.get(
            self.get_execution_list_url(self.project)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        execution_ids = [item['id'] for item in response.data]
        self.assertIn(current_execution.id, execution_ids)
        self.assertEqual(len(response.data), 1)
        self.assertNotIn('request_headers', response.data[0])
        self.assertNotIn('request_body', response.data[0])
        self.assertNotIn('response_headers', response.data[0])
        self.assertNotIn('response_body', response.data[0])

    def test_viewer_can_list_executions(self):
        execution = ApiTestExecution.objects.create(
            project=self.project,
            test_case=self.test_case,
            environment=self.environment,
            status=ApiTestExecution.Status.PENDING,
            executed_by=self.owner,
        )

        self.auth_as_viewer()
        response = self.client.get(
            self.get_execution_list_url(self.project)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], execution.id)

    def test_viewer_can_view_execution_detail(self):
        execution = ApiTestExecution.objects.create(
            project=self.project,
            test_case=self.test_case,
            environment=self.environment,
            status=ApiTestExecution.Status.FAILED,
            request_method='GET',
            request_url='http://test.example.com/api/users/18/',
            request_headers={'Authorization': 'Bearer ***'},
            request_query_params={'page': 1},
            response_status_code=200,
            response_body={'code': 1},
            failure_message='JSON 字段断言失败',
            executed_by=self.owner,
        )
        self.auth_as_viewer()

        response = self.client.get(
            self.get_execution_detail_url(self.project, execution)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], execution.id)
        self.assertEqual(response.data['request_method'], 'GET')
        self.assertEqual(
            response.data['request_headers']['Authorization'],
            'Bearer ***',
        )
        self.assertEqual(response.data['response_body'], {'code': 1})
        self.assertEqual(
            response.data['failure_message'],
            'JSON 字段断言失败',
        )

    def test_execution_detail_cannot_cross_projects(self):
        other_execution = ApiTestExecution.objects.create(
            project=self.other_project,
            test_case=self.other_test_case,
            status=ApiTestExecution.Status.PASSED,
            executed_by=self.owner,
        )
        self.auth_as_member()

        response = self.client.get(
            self.get_execution_detail_url(self.project, other_execution)
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('executions.views.execute_test_run_task.delay')
    def test_member_can_create_async_test_run(self, mock_delay):
        second_test_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Second batch case',
            expected_status_code=200,
            created_by=self.owner,
        )
        self.auth_as_member()

        response = self.client.post(
            self.get_test_run_list_url(self.project),
            {
                'name': 'Smoke Test',
                'test_case_ids': [self.test_case.id, second_test_case.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['status'], ApiTestRun.Status.PENDING)
        self.assertEqual(response.data['total_count'], 2)
        test_run = ApiTestRun.objects.get(pk=response.data['id'])
        self.assertEqual(
            set(test_run.test_cases.values_list('id',flat=True)),
            {self.test_case.id, second_test_case.id},
        )
        mock_delay.assert_called_once_with(test_run.id)

    @patch('executions.views.execute_test_run_task.delay')
    def test_viewer_cannot_create_test_run(self, mock_delay):
        self.auth_as_viewer()

        response = self.client.post(
            self.get_test_run_list_url(self.project),
            {'test_case_ids': [self.test_case.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(ApiTestRun.objects.count(), 0)
        mock_delay.assert_not_called()

    @patch('executions.views.execute_test_run_task.delay')
    def test_test_run_rejects_duplicate_case_ids(self, mock_delay):
        self.auth_as_member()

        response = self.client.post(
            self.get_test_run_list_url(self.project),
            {
                'test_case_ids': [self.test_case.id, self.test_case.id],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('test_case_ids', response.data)
        mock_delay.assert_not_called()

    @patch('executions.views.execute_test_run_task.delay')
    def test_test_run_rejects_case_from_other_project(self, mock_delay):
        self.auth_as_member()

        response = self.client.post(
            self.get_test_run_list_url(self.project),
            {'test_case_ids': [self.other_test_case.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['invalid_test_case_ids'],
            [self.other_test_case.id],
        )
        mock_delay.assert_not_called()

    def test_viewer_can_view_test_run_detail(self):
        test_run = ApiTestRun.objects.create(
            project=self.project,
            name='Regression',
            status=ApiTestRun.Status.COMPLETED,
            total_count=1,
            completed_count=1,
            passed_count=1,
            executed_by=self.owner,
        )
        test_run.test_cases.set([self.test_case])
        ApiTestExecution.objects.create(
            project=self.project,
            test_case=self.test_case,
            environment=self.environment,
            test_run=test_run,
            status=ApiTestExecution.Status.PASSED,
            executed_by=self.owner,
        )
        self.auth_as_viewer()

        response = self.client.get(
            self.get_test_run_detail_url(self.project, test_run)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], test_run.id)
        self.assertEqual(response.data['test_cases'][0]['id'], self.test_case.id)
        self.assertEqual(response.data['executions'][0]['test_run'], test_run.id)

    def test_test_run_detail_cannot_cross_projects(self):
        test_run = ApiTestRun.objects.create(
            project=self.other_project,
            total_count=1,
            executed_by=self.owner,
        )
        test_run.test_cases.set([self.other_test_case])
        self.auth_as_member()

        response = self.client.get(
            self.get_test_run_detail_url(self.project, test_run)
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('executions.services.requests.request')
    def test_execute_test_run_updates_counts_and_is_idempotent(self, mock_request):
        failed_test_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Expected 201 case',
            expected_status_code=201,
            created_by=self.owner,
        )
        test_run = ApiTestRun.objects.create(
            project=self.project,
            name='Count Test',
            total_count=2,
            executed_by=self.member,
        )
        test_run.test_cases.set([self.test_case, failed_test_case])
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.json.return_value = {'message': 'ok'}
        mock_request.return_value = mock_response

        execute_test_run(test_run.id)

        test_run.refresh_from_db()
        self.assertEqual(test_run.status, ApiTestRun.Status.COMPLETED)
        self.assertEqual(test_run.completed_count, 2)
        self.assertEqual(test_run.passed_count, 1)
        self.assertEqual(test_run.failed_count, 1)
        self.assertEqual(test_run.error_count, 0)
        self.assertEqual(test_run.executions.count(), 2)
        self.assertEqual(mock_request.call_count, 2)

        # 重复消费同一个任务不会再次发送 HTTP 请求或创建执行记录。
        execute_test_run(test_run.id)
        self.assertEqual(test_run.executions.count(), 2)
        self.assertEqual(mock_request.call_count, 2)

    def test_viewer_can_view_completed_test_run_report(self):
        failed_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Failed report case',
            expected_status_code=200,
            created_by=self.owner,
        )
        error_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Error report case',
            expected_status_code=200,
            created_by=self.owner,
        )
        test_run = ApiTestRun.objects.create(
            project=self.project,
            name='Report Test',
            status=ApiTestRun.Status.COMPLETED,
            total_count=3,
            completed_count=3,
            passed_count=1,
            failed_count=1,
            error_count=1,
            duration_ms=800,
            executed_by=self.owner,
        )
        test_run.test_cases.set([
            self.test_case,
            failed_case,
            error_case,
        ])
        ApiTestExecution.objects.create(
            project=self.project,
            test_case=self.test_case,
            environment=self.environment,
            test_run=test_run,
            status=ApiTestExecution.Status.PASSED,
            duration_ms=100,
            executed_by=self.owner,
        )
        failed_execution = ApiTestExecution.objects.create(
            project=self.project,
            test_case=failed_case,
            environment=self.environment,
            test_run=test_run,
            status=ApiTestExecution.Status.FAILED,
            response_status_code=200,
            duration_ms=300,
            failure_message='code 期望 0，实际 1001',
            executed_by=self.owner,
        )
        ApiTestExecution.objects.create(
            project=self.project,
            test_case=error_case,
            environment=self.environment,
            test_run=test_run,
            status=ApiTestExecution.Status.ERROR,
            error_message='request timed out',
            executed_by=self.owner,
        )
        self.auth_as_viewer()

        response = self.client.get(
            self.get_test_run_report_url(self.project, test_run)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['result'], 'failed')
        self.assertEqual(response.data['completion_rate'], 100.0)
        self.assertEqual(response.data['pass_rate'], 33.33)
        self.assertEqual(response.data['failure_rate'], 33.33)
        self.assertEqual(response.data['error_rate'], 33.33)
        self.assertEqual(response.data['total_duration_ms'], 800)
        self.assertEqual(response.data['average_duration_ms'], 200.0)
        self.assertEqual(response.data['max_duration_ms'], 300)
        self.assertEqual(
            response.data['slowest_executions'][0]['execution_id'],
            failed_execution.id,
        )
        self.assertEqual(len(response.data['problem_executions']), 2)
        self.assertNotIn('request_body', response.data['problem_executions'][0])
        self.assertNotIn('response_body', response.data['problem_executions'][0])

    def test_running_report_uses_completed_count_for_rates(self):
        test_run = ApiTestRun.objects.create(
            project=self.project,
            name='Running Report',
            status=ApiTestRun.Status.RUNNING,
            total_count=4,
            completed_count=2,
            passed_count=2,
            executed_by=self.owner,
        )
        self.auth_as_member()

        response = self.client.get(
            self.get_test_run_report_url(self.project, test_run)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['result'], 'incomplete')
        self.assertEqual(response.data['completion_rate'], 50.0)
        self.assertEqual(response.data['pass_rate'], 100.0)
        self.assertEqual(response.data['failure_rate'], 0.0)

    def test_completed_all_passed_report_result(self):
        test_run = ApiTestRun.objects.create(
            project=self.project,
            status=ApiTestRun.Status.COMPLETED,
            total_count=1,
            completed_count=1,
            passed_count=1,
            executed_by=self.owner,
        )
        self.auth_as_member()

        response = self.client.get(
            self.get_test_run_report_url(self.project, test_run)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['result'], 'passed')

    def test_test_run_report_cannot_cross_projects(self):
        test_run = ApiTestRun.objects.create(
            project=self.other_project,
            status=ApiTestRun.Status.COMPLETED,
            executed_by=self.owner,
        )
        self.auth_as_member()

        response = self.client.get(
            self.get_test_run_report_url(self.project, test_run)
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
