from PIL import Image
from django.db import models
from django.contrib.auth.models import (
	AbstractBaseUser, PermissionsMixin, BaseUserManager
)
from django.utils import timezone


class UserManager(BaseUserManager):
	def create_user(self, email, password=None, **extra_fields):
		if not email:
			raise ValueError('The Email must be set')
		email = self.normalize_email(email)
		user = self.model(email=email, **extra_fields)
		user.set_password(password)
		user.save(using=self._db)
		return user

	def create_superuser(self, email, password, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)
		extra_fields.setdefault('role', 'superuser')

		if extra_fields.get('is_staff') is not True:
			raise ValueError('Superuser must have is_staff=True')
		if extra_fields.get('is_superuser') is not True:
			raise ValueError('Superuser must have is_superuser=True')

		return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
	USER_ROLE_CHOICES = [
		('user', 'User (Resident)'),
		('block_admin', 'Block Administrator'),
		('superuser', 'Superuser'),
	]

	email = models.EmailField(unique=True)
	first_name = models.CharField(max_length=150, blank=True)
	last_name = models.CharField(max_length=150, blank=True)
	is_active = models.BooleanField(default=True)
	is_staff = models.BooleanField(default=False)
	role = models.CharField(max_length=20, choices=USER_ROLE_CHOICES, default='user')
	date_joined = models.DateTimeField(default=timezone.now)
	# optional profile picture
	profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
	receive_email_notifications = models.BooleanField(default=True, help_text="Receive email notifications for new bills and payments.")

	objects = UserManager()

	USERNAME_FIELD = 'email'
	REQUIRED_FIELDS = []

	def __str__(self):
		return self.email

	def save(self, *args, **kwargs):
		# Delete old image if a new one is uploaded
		if self.pk:
			try:
				old_profile = User.objects.get(pk=self.pk)
				if old_profile.profile_image and old_profile.profile_image != self.profile_image:
					old_profile.profile_image.delete(save=False)
			except User.DoesNotExist:
				pass

		super().save(*args, **kwargs)

		if self.profile_image:
			img = Image.open(self.profile_image.path)

			if img.height > 300 or img.width > 300:
				output_size = (300, 300)
				img.thumbnail(output_size)
				img.save(self.profile_image.path)

	@property
	def unread_notification_count(self):
		return self.notifications.filter(is_read=False).count()


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.recipient.email}"

    class Meta:
        ordering = ['-timestamp']
