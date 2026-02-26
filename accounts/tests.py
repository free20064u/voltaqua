from django.test import TestCase
from django.urls import reverse
from .models import User


class AccountsAuthTests(TestCase):
    def setUp(self):
        self.email = 'user@example.com'
        self.password = 'Testpass123'
        self.user = User.objects.create_user(email=self.email, password=self.password)

    def test_login_logout_flow(self):
        # login page loads
        resp = self.client.get(reverse('accounts:login'))
        self.assertEqual(resp.status_code, 200)
        # perform login
        resp = self.client.post(reverse('accounts:login'), {
            'username': self.email,
            'password': self.password,
        }, follow=True)
        self.assertTrue(resp.context['user'].is_authenticated)
        # logout
        resp = self.client.post(reverse('accounts:logout'), follow=True)
        self.assertFalse(resp.context['user'].is_authenticated)
        self.assertRedirects(resp, reverse('base:home'))

    def test_profile_image_upload(self):
        self.client.login(username=self.email, password=self.password)
        url = reverse('accounts:profile')
        # create a simple in-memory file
        from django.core.files.uploadedfile import SimpleUploadedFile
        image = SimpleUploadedFile('avatar.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        resp = self.client.post(url, {'first_name': 'New', 'last_name': 'Name', 'profile_image': image}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.profile_image))

