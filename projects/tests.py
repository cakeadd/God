from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User
from .models import Project, ProjectMember


class ProjectAPITests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner',
            password='owner123456',
        )
        self.member = User.objects.create_user(
            username='member',
            password='member123456',
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

    def auth_as_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.owner_access}')

    def auth_as_member(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.member_access}')

    def test_create_project_creates_owner_membership(self):
        self.auth_as_owner()

        response = self.client.post(
            reverse('project-list-create'),
            {
                'name': 'Project A',
                'description': 'First project',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Project A')
        self.assertEqual(response.data['owner'], self.owner.id)
        self.assertEqual(response.data['my_role'], ProjectMember.Role.OWNER)

        project = Project.objects.get(id=response.data['id'])
        self.assertTrue(
            ProjectMember.objects.filter(
                project=project,
                user=self.owner,
                role=ProjectMember.Role.OWNER,
            ).exists()
        )

    def test_list_only_returns_joined_projects(self):
        joined_project = Project.objects.create(
            name='Joined Project',
            description='Visible',
            owner=self.owner,
        )
        ProjectMember.objects.create(
            project=joined_project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )

        other_project = Project.objects.create(
            name='Other Project',
            description='Invisible',
            owner=self.member,
        )
        ProjectMember.objects.create(
            project=other_project,
            user=self.member,
            role=ProjectMember.Role.OWNER,
        )

        self.auth_as_owner()
        response = self.client.get(reverse('project-list-create'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [item['name'] for item in response.data]
        self.assertIn('Joined Project', names)
        self.assertNotIn('Other Project', names)

    def test_owner_can_update_project(self):
        project = Project.objects.create(
            name='Old Name',
            description='Old description',
            owner=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )

        self.auth_as_owner()
        response = self.client.patch(
            reverse('project-detail', kwargs={'pk': project.id}),
            {'description': 'New description'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['description'], 'New description')

    def test_member_cannot_update_project(self):
        project = Project.objects.create(
            name='Project A',
            description='Protected',
            owner=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.member,
            role=ProjectMember.Role.MEMBER,
        )

        self.auth_as_member()
        response = self.client.patch(
            reverse('project-detail', kwargs={'pk': project.id}),
            {'description': 'Member update'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_archive_project(self):
        project = Project.objects.create(
            name='Archive Project',
            description='To archive',
            owner=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )

        self.auth_as_owner()
        response = self.client.delete(
            reverse('project-detail', kwargs={'pk': project.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        project.refresh_from_db()
        self.assertTrue(project.is_archived)

    def test_archived_project_not_in_list(self):
        project = Project.objects.create(
            name='Archived Project',
            description='Hidden',
            owner=self.owner,
            is_archived=True,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )

        self.auth_as_owner()
        response = self.client.get(reverse('project-list-create'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])