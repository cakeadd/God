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
from .models import TestExecution as ApiTestExecution


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
            '测试用例没有可用的运行环境或 base_url',
        )

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
