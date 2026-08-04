from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from environments.models import Environment
from interfaces.models import ApiEndpoint
from projects.models import Project, ProjectMember
from users.models import User
from .models import TestCase as ApiTestCase


class TestCaseAPITests(APITestCase):
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
            path='/api/products/',
            headers={'Authorization': 'Bearer {{token}}'},
            query_params={'page': 1, 'size': 10},
            body={},
            created_by=self.owner,
        )

        self.environment = Environment.objects.create(
            project=self.project,
            name='Test Env',
            base_url='http://test.example.com',
            variables={'token': 'test-token'},
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

    def auth_as_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.member_access}')

    def auth_as_viewer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.viewer_access}')

    def get_testcase_list_url(self, project):
        return reverse(
            'testcase-list-create',
            kwargs={
                'project_id': project.id,
            },
        )

    def get_testcase_detail_url(self, project, test_case):
        return reverse(
            'testcase-detail',
            kwargs={
                'project_id': project.id,
                'pk': test_case.id,
            },
        )

    def test_member_can_create_testcase(self):
        self.auth_as_member()

        response = self.client.post(
            self.get_testcase_list_url(self.project),
            {
                'endpoint': self.endpoint.id,
                'environment': self.environment.id,
                'name': 'Product list success',
                'description': 'Check product list returns 200',
                'headers': {
                    'Authorization': 'Bearer {{token}}',
                },
                'query_params': {
                    'page': 1,
                    'size': 10,
                },
                'body': {},
                'expected_status_code': 200,
                'assertions': [
                    {
                        'type': 'status_code',
                        'expected': 200,
                    },
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Product list success')
        self.assertEqual(response.data['project'], self.project.id)
        self.assertEqual(response.data['endpoint'], self.endpoint.id)
        self.assertEqual(response.data['endpoint_name'], self.endpoint.name)
        self.assertEqual(response.data['environment'], self.environment.id)
        self.assertEqual(response.data['environment_name'], self.environment.name)
        self.assertEqual(response.data['created_by'], self.member.id)
        self.assertEqual(response.data['expected_status_code'], 200)

    def test_viewer_cannot_create_testcase(self):
        self.auth_as_viewer()

        response = self.client.post(
            self.get_testcase_list_url(self.project),
            {
                'endpoint': self.endpoint.id,
                'environment': self.environment.id,
                'name': 'Viewer testcase',
                'expected_status_code': 200,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_rejects_invalid_assertion(self):
        self.auth_as_member()

        response = self.client.post(
            self.get_testcase_list_url(self.project),
            {
                'endpoint': self.endpoint.id,
                'environment': self.environment.id,
                'name': 'Invalid assertion case',
                'expected_status_code': 200,
                'assertions': [
                    {
                        'type': 'json_field_contains',
                        'path': 'data.id',
                        'expected': 1,
                    },
                ],
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('assertions', response.data)

    def test_create_and_update_reject_duplicate_testcase_name(self):
        existing_test_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Existing Test Case',
            created_by=self.owner,
        )
        editable_test_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Editable Test Case',
            created_by=self.owner,
        )
        self.auth_as_member()

        create_response = self.client.post(
            self.get_testcase_list_url(self.project),
            {
                'endpoint': self.endpoint.id,
                'environment': self.environment.id,
                'name': existing_test_case.name,
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(create_response.data['name'][0]),
            '当前项目已存在同名测试用例，请修改用例名称后重试。',
        )

        update_response = self.client.patch(
            self.get_testcase_detail_url(self.project, editable_test_case),
            {'name': existing_test_case.name},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(update_response.data['name'][0]),
            '当前项目已存在同名测试用例，请修改用例名称后重试。',
        )

    def test_list_only_returns_active_testcases_in_project(self):
        active_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Active Case',
            expected_status_code=200,
            created_by=self.owner,
        )
        ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Inactive Case',
            expected_status_code=200,
            created_by=self.owner,
            is_active=False,
        )
        ApiTestCase.objects.create(
            project=self.other_project,
            endpoint=self.other_endpoint,
            name='Other Project Case',
            expected_status_code=200,
            created_by=self.owner,
        )

        self.auth_as_member()
        response = self.client.get(
            self.get_testcase_list_url(self.project)
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        names = [item['name'] for item in response.data]
        self.assertIn(active_case.name, names)
        self.assertNotIn('Inactive Case', names)
        self.assertNotIn('Other Project Case', names)

    def test_cannot_create_testcase_with_endpoint_from_other_project(self):
        self.auth_as_member()

        response = self.client.post(
            self.get_testcase_list_url(self.project),
            {
                'endpoint': self.other_endpoint.id,
                'environment': self.environment.id,
                'name': 'Invalid endpoint testcase',
                'expected_status_code': 200,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_member_can_update_testcase(self):
        test_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Old Case',
            description='Old description',
            query_params={'page': 1, 'size': 10},
            expected_status_code=200,
            created_by=self.owner,
        )

        self.auth_as_member()
        response = self.client.patch(
            self.get_testcase_detail_url(self.project, test_case),
            {
                'description': 'Updated description',
                'query_params': {
                    'page': 1,
                    'size': 20,
                },
                'expected_status_code': 201,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Updated description')
        self.assertEqual(response.data['query_params']['size'], 20)
        self.assertEqual(response.data['expected_status_code'], 201)

    def test_delete_deactivates_testcase(self):
        test_case = ApiTestCase.objects.create(
            project=self.project,
            endpoint=self.endpoint,
            environment=self.environment,
            name='Case To Delete',
            expected_status_code=200,
            created_by=self.owner,
        )

        self.auth_as_member()
        response = self.client.delete(
            self.get_testcase_detail_url(self.project, test_case),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        test_case.refresh_from_db()
        self.assertFalse(test_case.is_active)

        list_response = self.client.get(
            self.get_testcase_list_url(self.project)
        )

        self.assertEqual(list_response.data, [])
