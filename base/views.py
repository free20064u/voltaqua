from django.shortcuts import render, redirect
from django.core.mail import EmailMessage
from django.views.generic import TemplateView
from .forms import ContactForm

class HomeView(TemplateView):
    template_name = "base/home.html"

class AboutView(TemplateView):
    template_name = "base/about.html"

class TermsView(TemplateView):
    template_name = "base/terms.html"

class PrivacyView(TemplateView):
    template_name = "base/privacy.html"

def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            from_email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            email_message = EmailMessage(
                subject=f"[Voltaqua Contact] {subject}",
                body=f"From: {name} <{from_email}>\n\n{message}",
                from_email='contact-form@voltaqua.com',
                to=['admin@voltaqua.com'], # IMPORTANT: Change this to your support email
                reply_to=[from_email]
            )
            email_message.send()
            
            return redirect('base:contact_success')
    else:
        form = ContactForm()
    
    context = {
        'form': form,
        'title': 'Contact Us'
    }
    return render(request, 'base/contact.html', context)

def contact_success_view(request):
    return render(request, 'base/contact_success.html')