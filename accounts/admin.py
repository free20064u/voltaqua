from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User
from .forms import UserCreationForm, UserChangeForm


class UserAdmin(BaseUserAdmin):
	form = UserChangeForm
	add_form = UserCreationForm

	list_display = ('email', 'first_name', 'last_name', 'is_staff')
	list_filter = ('is_staff', 'is_superuser', 'is_active')
	fieldsets = (
		(None, {'fields': ('email', 'password')}),
		('Personal info', {'fields': ('first_name', 'last_name', 'profile_image')}),
		('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
	)
	add_fieldsets = (
		(None, {
			'classes': ('wide',),
			'fields': ('email', 'first_name', 'last_name', 'profile_image', 'password1', 'password2'),
		}),
	)
	search_fields = ('email', 'first_name', 'last_name')
	ordering = ('email',)
	filter_horizontal = ('groups', 'user_permissions')


admin.site.register(User, UserAdmin)
