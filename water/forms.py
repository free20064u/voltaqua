from django import forms
from .models import Apartment, Bill
from django.utils import timezone
from datetime import timedelta


class ApartmentForm(forms.ModelForm):
    """Form for block admins to update apartment occupants."""
    
    class Meta:
        model = Apartment
        fields = ['number', 'occupants']
        widgets = {
            'number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Apartment number (e.g., 01, 02, A1)',
                'readonly': True,
            }),
            'occupants': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of people living in this apartment',
                'min': '0',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['number'].disabled = True


class BillEntryForm(forms.Form):
    """Form for block admins to enter monthly bills for their block."""
    
    period_start = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        }),
        label='Billing Period Start',
        help_text='First day of the billing period',
    )
    
    period_end = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
        }),
        label='Billing Period End',
        help_text='Last day of the billing period',
    )
    
    total_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0',
        }),
        label='Total Block Bill Amount',
        help_text='Total water bill for the entire block. This will be distributed to apartments based on occupancy.',
    )

    total_volume = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '0',
        }),
        label='Total Water Volume (m³)',
        help_text='Total water volume consumed by the block in cubic meters (m³). This will be distributed to apartments based on occupancy.',
    )
    
    def __init__(self, site=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site = site
        
        # Set default dates for next month
        today = timezone.now().date()
        next_month = today.replace(day=1) + timedelta(days=32)
        next_month = next_month.replace(day=1)
        
        # Start of next month
        self.fields['period_start'].initial = next_month
        
        # End of next month
        if next_month.month == 12:
            end_of_month = next_month.replace(year=next_month.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_of_month = next_month.replace(month=next_month.month + 1, day=1) - timedelta(days=1)
        self.fields['period_end'].initial = end_of_month
    
    def clean(self):
        cleaned_data = super().clean()
        period_start = cleaned_data.get('period_start')
        period_end = cleaned_data.get('period_end')
        total_amount = cleaned_data.get('total_amount')
        total_volume = cleaned_data.get('total_volume')
        
        if period_start and period_end and period_start > period_end:
            raise forms.ValidationError('Period start date must be before period end date.')
        
        if total_amount and total_amount < 0:
            raise forms.ValidationError('Bill amount must be positive.')
            
        if total_volume and total_volume < 0:
            raise forms.ValidationError('Total volume must be positive.')
        
        return cleaned_data


class BillDistributionForm(forms.Form):
    """Form to review and confirm bill distribution to apartments."""
    
    confirm = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
        }),
        label='I confirm that the bill has been correctly distributed to all apartments based on occupancy.',
    )
