from django import forms
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.contrib.auth.forms import AuthenticationForm
from .models import User
from water.models import Apartment


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'profile_image', 'receive_email_notifications')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'receive_email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


from water.models import Apartment

class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        max_length=254,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autofocus': True})
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    remember_me = forms.BooleanField(
        label='Remember me',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean(self):
        cleaned_data = super().clean()
        user = self.user_cache
        if user is not None and user.role == 'user':
            try:
                apartment = Apartment.objects.get(user=user)
                if not apartment.is_active:
                    raise forms.ValidationError("Your apartment is not active. Please contact your block administrator.")
            except Apartment.DoesNotExist:
                # This should not happen for a 'user' role, but as a safeguard:
                raise forms.ValidationError("You are not associated with any apartment.")
        return cleaned_data


class UserCreationForm(forms.ModelForm):
    ROLE_CHOICES = (
        ('user', 'Resident (I want to join a block)'),
        ('block_admin', 'Block Admin (I want to manage a block)'),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=True,
        label="I am a..."
    )
    
    agreement = forms.ChoiceField(
        choices=[('agree', 'I agree')],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        required=True,
        label="Legal Agreement",
        error_messages={'required': 'You must agree to the terms and privacy policy to register.'}
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'role', 'profile_image')
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_image': forms.ClearableFileInput(attrs={'class': 'form-control'})
        }

    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    password2 = forms.CharField(
        label='Password confirmation',
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords don't match")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user


class UserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = ('email', 'password', 'first_name', 'last_name', 'profile_image', 'is_active', 'is_staff')

    def clean_password(self):
        return self.initial['password']
