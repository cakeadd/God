from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project,ProjectMember
from users.models import User
from .models import Environment

class EnvironmentAPITests(APITestCase):
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

    def environment_list_url(self,project):
        return reverse(
            'environment-list-create',
            kwargs={
                'project_id':project.id
            }
        )

    def environment_detail_url(self,project,environment):
        return reverse(
            'environment-detail',
            kwargs={
                'project_id':project.id,
                'pk':environment.id
            }
        )

    def test_member_can_create_environment(self):
        self.auth_as_member()

        response = self.client.post(
            self.environment_list_url(self.project),
            {
                'name': 'Test Env',
                'base_url': 'http://test.example.com',
                'variables': {
                    'token': 'test-token',
                    'user_id': 1,
                },
                'description': 'Test environment',
                'is_default': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Test Env')
        self.assertEqual(response.data['project'], self.project.id)
        self.assertEqual(response.data['variables']['token'], 'test-token')
        self.assertTrue(response.data['is_default'])

    def test_viewer_cannot_create_environment(self):
        self.auth_as_viewer()

        response = self.client.post(
            self.environment_list_url(self.project),
            {
                'name': 'Viewer Env',
                'base_url': 'http://viewer.example.com',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_only_returns_active_environments_in_project(self):
        active_environment = Environment.objects.create(
            project=self.project,
            name='Active Env',
            base_url='http://active.example.com',
        )
        Environment.objects.create(
            project=self.project,
            name='Inactive Env',
            base_url='http://inactive.example.com',
            is_active=False,
        )
        Environment.objects.create(
            project=self.other_project,
            name='Other Env',
            base_url='http://other.example.com',
        )

        self.auth_as_owner()
        response = self.client.get(self.environment_list_url(self.project))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item['name'] for item in response.data]
        self.assertIn(active_environment.name, names)
        self.assertNotIn('Inactive Env', names)
        self.assertNotIn('Other Env', names)

    def test_detail_cannot_cross_project(self):
        environment = Environment.objects.create(
            project=self.other_project,
            name='Other Env',
            base_url='http://other.example.com',
        )

        self.auth_as_owner()
        response = self.client.get(
            self.environment_detail_url(self.project, environment)
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_update_environment(self):
        environment = Environment.objects.create(
            project=self.project,
            name='Old Env',
            base_url='http://old.example.com',
            variables={'token': 'old-token'},
        )

        self.auth_as_member()
        response = self.client.patch(
            self.environment_detail_url(self.project, environment),
            {
                'base_url': 'http://new.example.com',
                'variables': {'token': 'new-token'},
                'description': 'Updated environment',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['base_url'], 'http://new.example.com')
        self.assertEqual(response.data['variables']['token'], 'new-token')
        self.assertEqual(response.data['description'], 'Updated environment')

    def test_delete_deactivates_environment(self):
        environment = Environment.objects.create(
            project=self.project,
            name='Env To Delete',
            base_url='http://delete.example.com',
        )

        self.auth_as_member()
        response = self.client.delete(
            self.environment_detail_url(self.project, environment)
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        environment.refresh_from_db()
        self.assertFalse(environment.is_active)

        list_response = self.client.get(self.environment_list_url(self.project))
        self.assertEqual(list_response.data, [])