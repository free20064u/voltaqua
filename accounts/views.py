from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout, login
from channels.layers import get_channel_layer
from .forms import UserCreationForm, ProfileForm, CustomAuthenticationForm
from .models import User, Notification


def login_view(request):
    """
    Handles user authentication and login session management.
    """
    if request.user.is_authenticated:
        return redirect('water:home')

    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # If 'Remember Me' is not checked, the session expires when the browser is closed.
            if not form.cleaned_data.get('remember_me'):
                request.session.set_expiry(0)

            messages.success(request, f"Welcome back, {user.first_name or user.email}!")

            next_page = request.POST.get('next') or request.GET.get('next')
            return redirect(next_page or 'water:home')
    else:
        form = CustomAuthenticationForm()

    context = {
        'form': form,
        'title': 'Log In — Voltaqua',
        'next': request.GET.get('next', '')
    }
    return render(request, 'accounts/login.html', context)


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)

            # --- Create and Send Notifications ---

            # 1. Create notifications in the database
            admin_roles = ['block_admin', 'superuser']
            admins = User.objects.filter(role__in=admin_roles)
            admin_message = f'A new user has just registered: {user.first_name or user.email}'
            for admin in admins:
                Notification.objects.create(recipient=admin, message=admin_message)

            welcome_message = f'Welcome to Voltaqua, {user.first_name}!'
            welcome_notification = Notification.objects.create(recipient=user, message=welcome_message)

            # 2. Send real-time notifications via Channels
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()

            # Notify admins
            async_to_sync(channel_layer.group_send)(
                'block_admins',
                {
                    'type': 'broadcast_message',
                    'message': {
                        'text': admin_message
                    }
                }
            )

            # Send a private welcome message to the new user
            async_to_sync(channel_layer.group_send)(
                f'user_{user.id}',
                {
                    'type': 'broadcast_message',
                    'message': {
                        'id': welcome_notification.id,
                        'text': welcome_notification.message
                    }
                }
            )

            messages.success(request, 'Registration successful! Welcome.')
            return redirect('water:home')
    else:
        form = UserCreationForm()
    
    context = {
        'form': form,
        'title': 'Create an Account'
    }
    return render(request, 'accounts/register.html', context)


@login_required
def notification_list(request):
    notifications = request.user.notifications.all()

    context = {
        'notifications': notifications,
        'title': 'My Notifications',
    }
    return render(request, 'accounts/notification_list.html', context)

@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, pk=notification_id, recipient=request.user)
    if request.method == 'POST':
        notification.is_read = True
        notification.save()
        messages.success(request, "Notification marked as read.")
    return redirect('accounts:notification_list')


@login_required
def mark_notifications_read(request):
    if request.method == 'POST':
        request.user.notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
    return redirect('accounts:notification_list')

@login_required
def profile(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=user)
    return render(request, 'accounts/profile.html', {'form': form, 'title': 'My Profile'})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect('base:home')