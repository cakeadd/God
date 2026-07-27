from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from executions.models import TestExecution as ExecutionRecord
from executions.models import TestRun as RunBatch
from interfaces.models import ApiEndpoint
from testcases.models import TestCase as CaseDefinition
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
        self.assertEqual(response.data['count'],3)
        self.assertEqual(
            [item['username'] for item in response.data['results']],
            ['owner', 'member', 'viewer'],
        )
        self.assertEqual(response.data['results'][0]['role'],ProjectMember.Role.OWNER)
        self.assertEqual(response.data['results'][2]['nickname'],'Viewer Name')

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
                self.assertEqual(response.data['count'],3)
                self.assertEqual(len(response.data['results']),3)

    def test_project_member_list_supports_pagination_and_owner_first(self):
        project=Project.objects.create(name='Paginated Members',owner=self.owner)
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )
        for index in range(5):
            user=User.objects.create(username=f'page-user-{index}')
            ProjectMember.objects.create(
                project=project,
                user=user,
                role=ProjectMember.Role.MEMBER,
            )

        self.auth_as_owner()
        first_page=self.client.get(
            reverse('project-member-list',kwargs={'project_id':project.id}),
            {'page':1,'page_size':2},
        )
        second_page=self.client.get(
            reverse('project-member-list',kwargs={'project_id':project.id}),
            {'page':2,'page_size':2},
        )

        self.assertEqual(first_page.status_code,status.HTTP_200_OK)
        self.assertEqual(first_page.data['count'],6)
        self.assertEqual(len(first_page.data['results']),2)
        self.assertEqual(first_page.data['results'][0]['role'],ProjectMember.Role.OWNER)
        self.assertEqual(len(second_page.data['results']),2)

    def test_project_member_list_searches_username_and_nickname(self):
        project, _, _, _ = self.create_shared_project()

        self.auth_as_owner()
        username_response=self.client.get(
            reverse('project-member-list',kwargs={'project_id':project.id}),
            {'search':'MEMB'},
        )
        nickname_response=self.client.get(
            reverse('project-member-list',kwargs={'project_id':project.id}),
            {'search':'viewer name'},
        )

        self.assertEqual(username_response.data['count'],1)
        self.assertEqual(
            username_response.data['results'][0]['username'],
            self.member.username,
        )
        self.assertEqual(nickname_response.data['count'],1)
        self.assertEqual(
            nickname_response.data['results'][0]['username'],
            self.viewer.username,
        )

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

    def test_owner_can_list_all_member_candidates_with_project_status(self):
        project, _, _, _ = self.create_shared_project()
        available_user = User.objects.create_user(
            username='available',
            password='available123456',
            nickname='Available User',
        )

        self.auth_as_owner()
        response = self.client.get(
            reverse(
                'project-member-candidate-list',
                kwargs={'project_id':project.id},
            ),
        )

        self.assertEqual(response.status_code,status.HTTP_200_OK)
        candidates={item['username']:item for item in response.data}
        self.assertEqual(set(candidates),{'owner','member','viewer','available'})
        self.assertTrue(candidates['owner']['is_project_member'])
        self.assertEqual(candidates['owner']['project_role'],ProjectMember.Role.OWNER)
        self.assertTrue(candidates['member']['is_project_member'])
        self.assertEqual(candidates['member']['project_role'],ProjectMember.Role.MEMBER)
        self.assertFalse(candidates[available_user.username]['is_project_member'])
        self.assertIsNone(candidates[available_user.username]['project_role'])
        self.assertNotIn('email',candidates[available_user.username])

    def test_member_and_viewer_cannot_list_member_candidates(self):
        project, _, _, _ = self.create_shared_project()
        url=reverse(
            'project-member-candidate-list',
            kwargs={'project_id':project.id},
        )

        for authenticate in [self.auth_as_member,self.auth_as_viewer]:
            with self.subTest(authenticate=authenticate.__name__):
                authenticate()
                response=self.client.get(url)
                self.assertEqual(response.status_code,status.HTTP_403_FORBIDDEN)

    def test_unrelated_user_cannot_list_member_candidates(self):
        project=Project.objects.create(name='Private Project',owner=self.owner)
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )

        self.auth_as_member()
        response=self.client.get(
            reverse(
                'project-member-candidate-list',
                kwargs={'project_id':project.id},
            ),
        )

        self.assertEqual(response.status_code,status.HTTP_404_NOT_FOUND)

    def test_owner_can_add_project_member_with_selected_role(self):
        project=Project.objects.create(name='Add Member Project',owner=self.owner)
        ProjectMember.objects.create(
            project=project,
            user=self.owner,
            role=ProjectMember.Role.OWNER,
        )

        self.auth_as_owner()
        response=self.client.post(
            reverse('project-member-list',kwargs={'project_id':project.id}),
            {'user':self.viewer.id,'role':ProjectMember.Role.VIEWER},
            format='json',
        )

        self.assertEqual(response.status_code,status.HTTP_201_CREATED)
        self.assertEqual(response.data['username'],self.viewer.username)
        self.assertEqual(response.data['role'],ProjectMember.Role.VIEWER)
        self.assertTrue(
            ProjectMember.objects.filter(
                project=project,
                user=self.viewer,
                role=ProjectMember.Role.VIEWER,
            ).exists()
        )

    def test_member_and_viewer_cannot_add_project_member(self):
        project, _, _, _ = self.create_shared_project()
        available_user=User.objects.create_user(
            username='available',
            password='available123456',
        )
        url=reverse('project-member-list',kwargs={'project_id':project.id})

        for authenticate in [self.auth_as_member,self.auth_as_viewer]:
            with self.subTest(authenticate=authenticate.__name__):
                authenticate()
                response=self.client.post(
                    url,
                    {'user':available_user.id,'role':ProjectMember.Role.MEMBER},
                    format='json',
                )
                self.assertEqual(response.status_code,status.HTTP_403_FORBIDDEN)

        self.assertFalse(
            ProjectMember.objects.filter(project=project,user=available_user).exists()
        )

    def test_owner_cannot_add_existing_member_or_assign_owner_role(self):
        project, _, member_membership, _ = self.create_shared_project()
        available_user=User.objects.create_user(
            username='available',
            password='available123456',
        )
        url=reverse('project-member-list',kwargs={'project_id':project.id})

        self.auth_as_owner()
        duplicate_response=self.client.post(
            url,
            {'user':member_membership.user_id,'role':ProjectMember.Role.MEMBER},
            format='json',
        )
        owner_role_response=self.client.post(
            url,
            {'user':available_user.id,'role':ProjectMember.Role.OWNER},
            format='json',
        )

        self.assertEqual(duplicate_response.status_code,status.HTTP_400_BAD_REQUEST)
        self.assertIn('user',duplicate_response.data)
        self.assertEqual(owner_role_response.status_code,status.HTTP_400_BAD_REQUEST)
        self.assertIn('role',owner_role_response.data)
        self.assertFalse(
            ProjectMember.objects.filter(project=project,user=available_user).exists()
        )

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

    def test_owner_can_remove_member_and_preserve_business_history(self):
        project, _, member_membership, _ = self.create_shared_project()
        endpoint = ApiEndpoint.objects.create(
            project=project,
            name='Member Endpoint',
            method=ApiEndpoint.Method.GET,
            path='/api/member-history/',
            created_by=self.member,
        )
        test_case = CaseDefinition.objects.create(
            project=project,
            endpoint=endpoint,
            name='Member Test Case',
            created_by=self.member,
        )
        test_run = RunBatch.objects.create(
            project=project,
            name='Running Member Batch',
            status=RunBatch.Status.RUNNING,
            total_count=1,
            executed_by=self.member,
        )
        test_run.test_cases.add(test_case)
        execution = ExecutionRecord.objects.create(
            project=project,
            test_case=test_case,
            test_run=test_run,
            status=ExecutionRecord.Status.RUNNING,
            executed_by=self.member,
        )

        self.auth_as_owner()
        response = self.client.delete(
            reverse(
                'project-member-detail',
                kwargs={
                    'project_id': project.id,
                    'member_id': member_membership.id,
                },
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProjectMember.objects.filter(pk=member_membership.id).exists())
        self.assertTrue(ApiEndpoint.objects.filter(pk=endpoint.id).exists())
        self.assertTrue(CaseDefinition.objects.filter(pk=test_case.id).exists())
        self.assertTrue(RunBatch.objects.filter(pk=test_run.id, status=RunBatch.Status.RUNNING).exists())
        self.assertTrue(
            ExecutionRecord.objects.filter(
                pk=execution.id,
                status=ExecutionRecord.Status.RUNNING,
            ).exists()
        )

        self.auth_as_member()
        project_response = self.client.get(
            reverse('project-detail', kwargs={'pk': project.id}),
        )
        self.assertEqual(project_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_and_viewer_cannot_remove_member(self):
        project, _, member_membership, _ = self.create_shared_project()
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
                response = self.client.delete(url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.assertTrue(ProjectMember.objects.filter(pk=member_membership.id).exists())

    def test_unrelated_user_cannot_remove_member(self):
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
        response = self.client.delete(
            reverse(
                'project-member-detail',
                kwargs={
                    'project_id': project.id,
                    'member_id': member_membership.id,
                },
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ProjectMember.objects.filter(pk=member_membership.id).exists())

    def test_owner_cannot_remove_member_from_another_project(self):
        project, _, _, _ = self.create_shared_project()
        other_project = Project.objects.create(
            name='Other Project For Removal',
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
        response = self.client.delete(
            reverse(
                'project-member-detail',
                kwargs={
                    'project_id': project.id,
                    'member_id': other_membership.id,
                },
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ProjectMember.objects.filter(pk=other_membership.id).exists())

    def test_owner_cannot_remove_project_owner(self):
        project, owner_membership, _, _ = self.create_shared_project()

        self.auth_as_owner()
        response = self.client.delete(
            reverse(
                'project-member-detail',
                kwargs={
                    'project_id': project.id,
                    'member_id': owner_membership.id,
                },
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], '不能移除项目拥有者')
        self.assertTrue(ProjectMember.objects.filter(pk=owner_membership.id).exists())
