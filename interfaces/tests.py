from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project,ProjectMember
from users.models import User
from .models import ApiEndpoint

class ApiEndpointAPITests(APITestCase):
    def setUp(self):
        self.owner=User.objects.create_user(
            username='owner',
            password='owner123456'
        )
        self.member = User.objects.create_user(
            username='member',
            password='member123456',
        )
        self.viewer = User.objects.create_user(
            username='viewer',
            password='viewer123456',
        )

        self.project=Project.objects.create(
            name='Project A',
            description='Test project',
            owner=self.owner
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.owner,
            role=ProjectMember.Role.OWNER
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.member,
            role=ProjectMember.Role.MEMBER
        )
        ProjectMember.objects.create(
            project=self.project,
            user=self.viewer,
            role=ProjectMember.Role.VIEWER
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

        owner_login = self.client.post(
            reverse('token-obtain-pair'),
            {
                'username': 'owner',
                'password': 'owner123456',
            },
            format='json',
        )
        self.owner_access = owner_login.data['access']

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

    def auth_as_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.owner_access}')

    def auth_as_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.member_access}')

    def auth_as_viewer(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.viewer_access}')

    def endpoint_list_url(self, project):
        return reverse(
            'api-endpoint-list-create',
            kwargs={'project_id': project.id},
        )

    def endpoint_detail_url(self, project, endpoint):
        return reverse(
            'api-endpoint-detail',
            kwargs={
                'project_id': project.id,
                'pk': endpoint.id,
            },
        )

    def test_member_can_create_endpoint(self):
        self.auth_as_member()

        response = self.client.post(
            self.endpoint_list_url(self.project),
            {
                'name': 'Product List',
                'method': 'GET',
                'path': '/api/products/',
                'description': 'List products',
                'headers': {'Authorization': 'Bearer {{token}}'},
                'query_params': {'page': 1, 'size': 10},
                'body': {},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Product List')
        self.assertEqual(response.data['project'], self.project.id)
        self.assertEqual(response.data['created_by'], self.member.id)

    def test_viewer_cannot_create_endpoint(self):
        self.auth_as_viewer()

        response = self.client.post(
            self.endpoint_list_url(self.project),
            {
                'name': 'Product List',
                'method': 'GET',
                'path': '/api/products/',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_only_returns_active_endpoints_in_project(self):
        active_endpoint = ApiEndpoint.objects.create(
            project=self.project,
            name='Active Endpoint',
            method=ApiEndpoint.Method.GET,
            path='/api/active/',
            created_by=self.owner,
        )
        ApiEndpoint.objects.create(
            project=self.project,
            name='Inactive Endpoint',
            method=ApiEndpoint.Method.GET,
            path='/api/inactive/',
            created_by=self.owner,
            is_active=False,
        )
        ApiEndpoint.objects.create(
            project=self.other_project,
            name='Other Project Endpoint',
            method=ApiEndpoint.Method.GET,
            path='/api/other/',
            created_by=self.owner,
        )

        self.auth_as_owner()
        response = self.client.get(self.endpoint_list_url(self.project))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item['name'] for item in response.data]
        self.assertIn(active_endpoint.name, names)
        self.assertNotIn('Inactive Endpoint', names)
        self.assertNotIn('Other Project Endpoint', names)

    def test_detail_cannot_cross_project(self):
        endpoint = ApiEndpoint.objects.create(
            project=self.other_project,
            name='Other Endpoint',
            method=ApiEndpoint.Method.GET,
            path='/api/other/',
            created_by=self.owner,
        )

        self.auth_as_owner()
        response = self.client.get(self.endpoint_detail_url(self.project, endpoint))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_update_endpoint(self):
        endpoint = ApiEndpoint.objects.create(
            project=self.project,
            name='Old Endpoint',
            method=ApiEndpoint.Method.GET,
            path='/api/old/',
            created_by=self.owner,
        )

        self.auth_as_member()
        response = self.client.patch(
            self.endpoint_detail_url(self.project, endpoint),
            {
                'description': 'Updated by member',
                'query_params': {'page': 1, 'size': 20},
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'Updated by member')
        self.assertEqual(response.data['query_params']['size'], 20)

    def test_delete_deactivates_endpoint(self):
        endpoint = ApiEndpoint.objects.create(
            project=self.project,
            name='Endpoint To Delete',
            method=ApiEndpoint.Method.GET,
            path='/api/delete/',
            created_by=self.owner,
        )

        self.auth_as_member()
        response = self.client.delete(self.endpoint_detail_url(self.project, endpoint))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        endpoint.refresh_from_db()
        self.assertFalse(endpoint.is_active)

        list_response = self.client.get(self.endpoint_list_url(self.project))
        self.assertEqual(list_response.data, [])
