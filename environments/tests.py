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

    def test_variables_must_be_json_object(self):
        environment = Environment.objects.create(
            project=self.project,
            name='Existing Env',
            base_url='http://existing.example.com',
        )
        self.auth_as_member()

        create_response = self.client.post(
            self.environment_list_url(self.project),
            {
                'name': 'Invalid Variables Env',
                'base_url': 'http://invalid.example.com',
                'variables': ['token', 'invalid'],
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('variables', create_response.data)

        update_response = self.client.patch(
            self.environment_detail_url(self.project, environment),
            {'variables': 'invalid'},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('variables', update_response.data)

    def test_create_and_update_reject_duplicate_environment_name(self):
        existing_environment = Environment.objects.create(
            project=self.project,
            name='Existing Env',
            base_url='http://existing.example.com',
        )
        editable_environment = Environment.objects.create(
            project=self.project,
            name='Editable Env',
            base_url='http://editable.example.com',
        )
        self.auth_as_member()

        create_response = self.client.post(
            self.environment_list_url(self.project),
            {
                'name': existing_environment.name,
                'base_url': 'http://duplicate.example.com',
            },
            format='json',
        )
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(create_response.data['name'][0]),
            '当前项目已存在同名环境，请修改环境名称后重试。',
        )

        update_response = self.client.patch(
            self.environment_detail_url(self.project, editable_environment),
            {'name': existing_environment.name},
            format='json',
        )
        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            str(update_response.data['name'][0]),
            '当前项目已存在同名环境，请修改环境名称后重试。',
        )

    def test_first_environment_becomes_default_automatically(self):
        self.auth_as_member()

        response = self.client.post(
            self.environment_list_url(self.project),
            {
                'name': 'First Env',
                'base_url': 'http://first.example.com',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_default'])

    def test_creating_new_default_unsets_old_default(self):
        old_default = Environment.objects.create(
            project=self.project,
            name='Old Default',
            base_url='http://old.example.com',
            is_default=True,
        )
        self.auth_as_member()

        response = self.client.post(
            self.environment_list_url(self.project),
            {
                'name': 'New Default',
                'base_url': 'http://new.example.com',
                'is_default': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_default'])
        old_default.refresh_from_db()
        self.assertFalse(old_default.is_default)

    def test_setting_another_environment_as_default_unsets_old_default(self):
        old_default = Environment.objects.create(
            project=self.project,
            name='Old Default',
            base_url='http://old.example.com',
            is_default=True,
        )
        new_default = Environment.objects.create(
            project=self.project,
            name='New Default',
            base_url='http://new.example.com',
        )
        self.auth_as_member()

        response = self.client.patch(
            self.environment_detail_url(self.project, new_default),
            {'is_default': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_default'])
        old_default.refresh_from_db()
        self.assertFalse(old_default.is_default)

    def test_cannot_unset_default_while_other_environment_is_active(self):
        default_environment = Environment.objects.create(
            project=self.project,
            name='Default Env',
            base_url='http://default.example.com',
            is_default=True,
        )
        Environment.objects.create(
            project=self.project,
            name='Other Env',
            base_url='http://other.example.com',
        )
        self.auth_as_member()

        response = self.client.patch(
            self.environment_detail_url(self.project, default_environment),
            {'is_default': False},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        default_environment.refresh_from_db()
        self.assertTrue(default_environment.is_default)

    def test_cannot_delete_default_while_other_environment_is_active(self):
        default_environment = Environment.objects.create(
            project=self.project,
            name='Default Env',
            base_url='http://default.example.com',
            is_default=True,
        )
        Environment.objects.create(
            project=self.project,
            name='Other Env',
            base_url='http://other.example.com',
        )
        self.auth_as_member()

        response = self.client.delete(
            self.environment_detail_url(self.project, default_environment)
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        default_environment.refresh_from_db()
        self.assertTrue(default_environment.is_active)

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
        self.assertEqual(response.data['count'], 1)
        names = [item['name'] for item in response.data['results']]
        self.assertIn(active_environment.name, names)
        self.assertNotIn('Inactive Env', names)
        self.assertNotIn('Other Env', names)

    def test_list_is_paginated_and_default_environment_is_first(self):
        default_environment = Environment.objects.create(
            project=self.project,
            name='Default Env',
            base_url='http://default.example.com',
            is_default=True,
        )
        for index in range(10):
            Environment.objects.create(
                project=self.project,
                name=f'Env {index}',
                base_url=f'http://env-{index}.example.com',
            )

        self.auth_as_owner()
        response = self.client.get(self.environment_list_url(self.project))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 10)
        self.assertEqual(response.data['results'][0]['id'], default_environment.id)
        self.assertIsNotNone(response.data['next'])
        self.assertIsNone(response.data['previous'])

        second_page_response = self.client.get(
            f'{self.environment_list_url(self.project)}?page=2'
        )
        self.assertEqual(second_page_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(second_page_response.data['results']), 1)
        self.assertIsNotNone(second_page_response.data['previous'])

    def test_list_accepts_custom_page_size(self):
        for index in range(3):
            Environment.objects.create(
                project=self.project,
                name=f'Env {index}',
                base_url=f'http://env-{index}.example.com',
            )

        self.auth_as_owner()
        response = self.client.get(
            f'{self.environment_list_url(self.project)}?page_size=2'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_searches_active_environment_name_before_pagination(self):
        matched_environment = Environment.objects.create(
            project=self.project,
            name='Staging Environment',
            base_url='http://staging.example.com',
        )
        Environment.objects.create(
            project=self.project,
            name='Inactive Staging Environment',
            base_url='http://inactive-staging.example.com',
            is_active=False,
        )
        Environment.objects.create(
            project=self.other_project,
            name='Other Staging Environment',
            base_url='http://other-staging.example.com',
        )

        self.auth_as_owner()
        response = self.client.get(
            f'{self.environment_list_url(self.project)}?search=staging'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], matched_environment.id)

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
            is_default=True,
        )

        self.auth_as_member()
        response = self.client.delete(
            self.environment_detail_url(self.project, environment)
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        environment.refresh_from_db()
        self.assertFalse(environment.is_active)

        list_response = self.client.get(self.environment_list_url(self.project))
        self.assertEqual(list_response.data['count'], 0)
        self.assertEqual(list_response.data['results'], [])

        detail_response = self.client.get(
            self.environment_detail_url(self.project, environment)
        )
        self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_viewer_cannot_deactivate_environment(self):
        environment = Environment.objects.create(
            project=self.project,
            name='Protected Env',
            base_url='http://protected.example.com',
            is_default=True,
        )
        self.auth_as_viewer()

        response = self.client.delete(
            self.environment_detail_url(self.project, environment)
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        environment.refresh_from_db()
        self.assertTrue(environment.is_active)
