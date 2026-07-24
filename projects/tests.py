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
        self.viewer = User.objects.create_user(
            username='viewer',
            password='viewer123456',
            nickname='Viewer Name',
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

    def create_shared_project(self):
        project = Project.objects.create(
            name='Shared Project',
            owner=self.owner,
        )
        owner_membership = ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )
        member_membership = ProjectMember.objects.create(
            project=project,
            user=self.member,
            role=ProjectMember.Role.MEMBER,
        )
        viewer_membership = ProjectMember.objects.create(
            project=project,
            user=self.viewer,
            role=ProjectMember.Role.VIEWER,
        )
        return project, owner_membership, member_membership, viewer_membership

    def test_project_roles_only_include_owner_member_viewer(self):
        self.assertEqual(
            ProjectMember.Role.values,
            ['owner','member','viewer'],
        )

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

    def test_project_member_list_returns_all_members_with_owner_first(self):
        project = Project.objects.create(
            name='Member List Project',
            owner=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.member,
            role=ProjectMember.Role.MEMBER,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.viewer,
            role=ProjectMember.Role.VIEWER,
        )

        self.auth_as_owner()
        response = self.client.get(
            reverse('project-member-list', kwargs={'project_id': project.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item['username'] for item in response.data],
            ['owner', 'member', 'viewer'],
        )
        self.assertEqual(response.data[0]['role'], ProjectMember.Role.OWNER)
        self.assertEqual(response.data[2]['nickname'], 'Viewer Name')

    def test_member_and_viewer_can_list_project_members(self):
        project = Project.objects.create(
            name='Shared Project',
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
        ProjectMember.objects.create(
            project=project,
            user=self.viewer,
            role=ProjectMember.Role.VIEWER,
        )
        url = reverse('project-member-list', kwargs={'project_id': project.id})

        for authenticate in [self.auth_as_member, self.auth_as_viewer]:
            with self.subTest(authenticate=authenticate.__name__):
                authenticate()
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(len(response.data), 3)

    def test_unrelated_user_cannot_list_project_members(self):
        project = Project.objects.create(
            name='Private Project',
            owner=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )

        self.auth_as_member()
        response = self.client.get(
            reverse('project-member-list', kwargs={'project_id': project.id}),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_update_member_role(self):
        project, _, member_membership, _ = self.create_shared_project()

        self.auth_as_owner()
        response = self.client.patch(
            reverse(
                'project-member-detail',
                kwargs={
                    'project_id': project.id,
                    'member_id': member_membership.id,
                },
            ),
            {'role': ProjectMember.Role.VIEWER},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['role'], ProjectMember.Role.VIEWER)
        self.assertEqual(response.data['username'], self.member.username)
        member_membership.refresh_from_db()
        self.assertEqual(member_membership.role, ProjectMember.Role.VIEWER)

    def test_member_and_viewer_cannot_update_member_role(self):
        project, _, member_membership, viewer_membership = self.create_shared_project()
        url = reverse(
            'project-member-detail',
            kwargs={
                'project_id': project.id,
                'member_id': member_membership.id,
            },
        )

        for authenticate in [self.auth_as_member, self.auth_as_viewer]:
            with self.subTest(authenticate=authenticate.__name__):
                authenticate()
                response = self.client.patch(
                    url,
                    {'role': ProjectMember.Role.VIEWER},
                    format='json',
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        member_membership.refresh_from_db()
        viewer_membership.refresh_from_db()
        self.assertEqual(member_membership.role, ProjectMember.Role.MEMBER)
        self.assertEqual(viewer_membership.role, ProjectMember.Role.VIEWER)

    def test_unrelated_user_cannot_update_member_role(self):
        project = Project.objects.create(
            name='Private Project',
            owner=self.owner,
        )
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )
        member_membership = ProjectMember.objects.create(
            project=project,
            user=self.member,
            role=ProjectMember.Role.MEMBER,
        )

        self.auth_as_viewer()
        response = self.client.patch(
            reverse(
                'project-member-detail',
                kwargs={
                    'project_id': project.id,
                    'member_id': member_membership.id,
                },
            ),
            {'role': ProjectMember.Role.VIEWER},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_cannot_update_member_from_another_project(self):
        project, _, _, _ = self.create_shared_project()
        other_project = Project.objects.create(
            name='Other Project',
            owner=self.member,
        )
        ProjectMember.objects.create(
            project=other_project,
            user=self.member,
            role=ProjectMember.Role.OWNER,
        )
        other_membership = ProjectMember.objects.create(
            project=other_project,
            user=self.viewer,
            role=ProjectMember.Role.MEMBER,
        )

        self.auth_as_owner()
        response = self.client.patch(
            reverse(
                'project-member-detail',
                kwargs={
                    'project_id': project.id,
                    'member_id': other_membership.id,
                },
            ),
            {'role': ProjectMember.Role.VIEWER},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_role_cannot_be_changed(self):
        project, owner_membership, _, _ = self.create_shared_project()

        self.auth_as_owner()
        response = self.client.patch(
            reverse(
                'project-member-detail',
                kwargs={
                    'project_id': project.id,
                    'member_id': owner_membership.id,
                },
            ),
            {'role': ProjectMember.Role.MEMBER},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)
        owner_membership.refresh_from_db()
        self.assertEqual(owner_membership.role, ProjectMember.Role.OWNER)

    def test_member_cannot_be_promoted_to_owner(self):
        project, _, member_membership, _ = self.create_shared_project()

        self.auth_as_owner()
        response = self.client.patch(
            reverse(
                'project-member-detail',
                kwargs={
                    'project_id': project.id,
                    'member_id': member_membership.id,
                },
            ),
            {'role': ProjectMember.Role.OWNER},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)
        member_membership.refresh_from_db()
        self.assertEqual(member_membership.role, ProjectMember.Role.MEMBER)
