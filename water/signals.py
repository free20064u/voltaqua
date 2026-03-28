from django.db.models.signals import post_save
from .models import Bill, Payment
from accounts.models import Notification
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


def get_models_to_watch():
    """Returns a list of models that should trigger a notification on save."""
    return [Bill, Payment]


def broadcast_data_update(sender, instance, **kwargs):
    """
    Creates a DB notification and sends an email for new Bills and Payments.
    """
    created = kwargs.get('created', False)

    # --- Part 1: Create DB Notification and send Email (for new Bill and Payment) ---
    if created:
        user_to_notify = None
        message = ""
        subject = ""
        html_template = ""
        text_template = ""
        context = {}

        if sender is Bill:
            bill = instance
            if bill.apartment and bill.apartment.user:
                user_to_notify = bill.apartment.user
                subject = f"New Water Bill from Voltaqua"
                message = f"New Water Bill: {bill.currency} {bill.total_bill} for period {bill.period_start} to {bill.period_end}"
                html_template = 'water/email/new_bill_notification.html'
                text_template = 'water/email/new_bill_notification.txt'
                context = {'user': user_to_notify, 'bill': bill}

        elif sender is Payment:
            payment = instance
            bill = payment.bill
            if bill.apartment and bill.apartment.user:
                user_to_notify = bill.apartment.user
                subject = f"Payment Received for Bill #{bill.id}"
                message = f"Payment Received: {bill.currency} {payment.amount} for Bill #{bill.id}"
                html_template = 'water/email/new_payment_notification.html'
                text_template = 'water/email/new_payment_notification.txt'
                context = {'user': user_to_notify, 'payment': payment, 'bill': bill}

        if user_to_notify and message:
            # Create DB notification
            Notification.objects.create(recipient=user_to_notify, message=message)

            # Send email notification
            # Safely check for email preference field
            receive_email = getattr(user_to_notify, 'receive_email_notifications', True)
            if user_to_notify.email and receive_email and subject and html_template and text_template:
                try:
                    html_message = render_to_string(html_template, context)
                    plain_message = render_to_string(text_template, context)
                    send_mail(
                        subject,
                        plain_message,
                        settings.DEFAULT_FROM_EMAIL,
                        [user_to_notify.email],
                        html_message=html_message,
                        fail_silently=False, # Set to True in production if email failure is acceptable
                    )
                except Exception:
                    # You might want to log this error in a real-world scenario
                    pass


for model in get_models_to_watch():
    post_save.connect(broadcast_data_update, sender=model, dispatch_uid=f"broadcast_update_{model.__name__}")
