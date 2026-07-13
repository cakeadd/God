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