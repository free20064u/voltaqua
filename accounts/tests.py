from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
import tempfile
import shutil
from unittest.mock import patch

from .models import User
from water.models import Site, Apartment


@override_settings(DEFAULT_FILE_STORAGE='django.core.files.storage.FileSystemStorage')
class AccountsAuthTests(TestCase):
    def setUp(self):
        self.email = 'user@example.com'
        self.password = 'Testpass123'
        self.user = User.objects.create_user(email=self.email, password=self.password)
        self.site = Site.objects.create(name='Test Site', code='TS')
        self.apartment = Apartment.objects.create(number='1', site=self.site, user=self.user, is_active=True)

        # Create a temporary directory for media files and override MEDIA_ROOT
        self.temp_media_dir = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media_dir)
        self.media_override.enable()

    def tearDown(self):
        self.media_override.disable()
        shutil.rmtree(self.temp_media_dir)
        super().tearDown()

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

    @patch('cloudinary.uploader.upload')
    def test_profile_image_upload(self, mock_upload):
        mock_upload.return_value = {
            'public_id': 'test_id',
            'version': '12345',
            'signature': 'test_signature',
            'width': 1,
            'height': 1,
            'format': 'png',
            'resource_type': 'image',
            'created_at': '2022-01-01T00:00:00Z',
            'tags': [],
            'bytes': 1,
            'type': 'upload',
            'etag': 'test_etag',
            'placeholder': False,
            'url': 'http://res.cloudinary.com/demo/image/upload/v12345/test_id.png',
            'secure_url': 'https://res.cloudinary.com/demo/image/upload/v12345/test_id.png',
            'original_filename': 'avatar'
        }
        self.client.force_login(self.user)
        url = reverse('accounts:profile')
        # create a simple in-memory file
        image = SimpleUploadedFile('avatar.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        resp = self.client.post(url, {'first_name': 'New', 'last_name': 'Name', 'profile_image': image}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(bool(self.user.profile_image))
