from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class AuthAPITests(APITestCase):
    def test_register_returns_user_and_token(self):
        resp=self.client.post(
            reverse('user-register'),
            {
                'username':'tester',
                'email': 'tester@example.com',
                'nickname': 'Tester',
                'password': 'testpass123',
                'password_confirm': 'testpass123',
            },
            format='json'
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['user']['username'],'tester')
        self.assertIn('access',resp.data)
        self.assertIn('refresh',resp.data)
        self.assertTrue(User.objects.filter(username='tester').exists())


    def test_login_returns_tokens(self):
        User.objects.create_user(username='tester',password='testpass123')

        resp=self.client.post(
            reverse('token-obtain-pair'),
            {
                'username':'tester',
                'password':'testpass123',
            },
            format='json'
        )

        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_me_requires_authentication(self):
        response = self.client.get(reverse('user-me'))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_current_user_with_token(self):
        user = User.objects.create_user(username='tester', password='testpass123')
        login_response = self.client.post(
            reverse('token-obtain-pair'),
            {
                'username': 'tester',
                'password': 'testpass123',
            },
            format='json',
        )
        access = login_response.data['access']

        response = self.client.get(
            reverse('user-me'),
            HTTP_AUTHORIZATION=f'Bearer {access}',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], user.id)
        self.assertEqual(response.data['username'], 'tester')

    def test_me_patch_updates_only_editable_profile_fields(self):
        user = User.objects.create_user(
            username='tester',
            password='testpass123',
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            reverse('user-me'),
            {
                'username': 'changed-username',
                'nickname': 'Updated Tester',
                'email': 'updated@example.com',
                'phone': '13800138000',
                'password': 'changed-password',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.username, 'tester')
        self.assertEqual(user.nickname, 'Updated Tester')
        self.assertEqual(user.email, 'updated@example.com')
        self.assertEqual(user.phone, '13800138000')
        self.assertTrue(user.check_password('testpass123'))
        self.assertNotIn('password', response.data)

    def test_me_patch_rejects_duplicate_phone(self):
        User.objects.create_user(
            username='existing',
            password='testpass123',
            phone='13800138000',
        )
        user = User.objects.create_user(
            username='tester',
            password='testpass123',
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            reverse('user-me'),
            {'phone': '13800138000'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_me_patch_converts_empty_phone_to_null(self):
        user = User.objects.create_user(
            username='tester',
            password='testpass123',
            phone='13800138000',
        )
        self.client.force_authenticate(user=user)

        response = self.client.patch(
            reverse('user-me'),
            {'phone': ''},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertIsNone(user.phone)
        self.assertIsNone(response.data['phone'])

    def test_me_patch_requires_authentication(self):
        response = self.client.patch(
            reverse('user-me'),
            {'nickname': 'Anonymous'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
