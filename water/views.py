from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from decimal import Decimal, ROUND_HALF_UP
from django.contrib import messages
from datetime import timedelta
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model

from .models import (
    Site,
    Apartment,
    Meter,
    ConsumptionSummary,
    Bill,
    BillOccupancy,
    Payment,
)
from dustbin.models import DustbinBill
from .forms import ApartmentForm, BillEntryForm, PaymentForm


def _apply_bill_payment_status(bill, total_paid=None, save=False):
    """Return the bill's live balance/status and optionally persist status changes."""
    if total_paid is None:
        total_paid = bill.payments.aggregate(Sum('amount')).get('amount__sum') or Decimal('0')

    total_paid = Decimal(total_paid)
    raw_balance = bill.total_bill - total_paid
    balance = max(raw_balance, Decimal('0'))
    status = 'paid' if raw_balance <= Decimal('0') else 'pending'
    previous_status = bill.status

    bill.total_paid = total_paid
    bill.balance = balance
    bill.status = status

    if save and previous_status != status:
        bill.save(update_fields=['status'])

    return balance, status


def _settle_bills_with_carryover(bills, save=False):
    """Apply overpayments as carry-forward credit across a sequence of bills."""
    credit = Decimal('0')
    settled_bills = []

    for bill in bills:
        total_paid = Decimal(getattr(bill, 'total_paid', Decimal('0')) or Decimal('0'))
        effective_paid = total_paid + credit
        raw_balance = bill.total_bill - effective_paid
        balance = max(raw_balance, Decimal('0'))
        status = 'paid' if raw_balance <= Decimal('0') else 'pending'
        previous_status = bill.status

        bill.effective_paid = min(effective_paid, bill.total_bill)
        bill.credit_applied = min(credit, bill.total_bill)
        bill.total_paid = total_paid
        bill.balance = balance
        bill.status = status

        if save and previous_status != status:
            bill.save(update_fields=['status'])

        credit = max(effective_paid - bill.total_bill, Decimal('0'))
        bill.carryover_credit = credit
        settled_bills.append(bill)

    return settled_bills


def _get_bills_for_outstanding_calculation(qs_bills):
    """Return bills with live balances after apartment-level credit carry-forward."""
    annotated_bills = list(
        qs_bills.select_related('apartment').annotate(
            total_paid=Coalesce(Sum('payments__amount'), 0, output_field=models.DecimalField())
        ).order_by('apartment_id', 'period_end', 'issued_at', 'id')
    )

    grouped_bills = []
    current_group = []
    current_group_key = None

    for bill in annotated_bills:
        group_key = bill.apartment_id if bill.apartment_id is not None else f"bill-{bill.id}"
        if group_key != current_group_key and current_group:
            grouped_bills.extend(_settle_bills_with_carryover(current_group))
            current_group = []
        current_group.append(bill)
        current_group_key = group_key

    if current_group:
        grouped_bills.extend(_settle_bills_with_carryover(current_group))

    return grouped_bills


def _can_view_site(user, site):
    """Check if user can view a site (block) dashboard.

    - Superusers can view any site.
    - Block admins can only view their assigned site.
    - Regular users cannot view site dashboards.
    """
    if user.role == 'superuser':
        return True
    if user.role == 'block_admin' and site.user_id == user.id:
        return True
    return False


def _can_view_apartment(user, apartment):
    """Check if user can view an apartment dashboard.

    - Superusers can view any apartment.
    - Block admins can view apartments in their assigned site.
    - Regular users can view their own apartment.
    """
    if user.role == 'superuser':
        return True
    if user.role == 'block_admin' and apartment.site.user_id == user.id:
        return True
    if user.role == 'user' and apartment.user_id == user.id:
        return True
    return False


# helper used by all dashboards

def _gather_stats(site=None, apartment=None):
    """Return stats dict filtered by `site` or `apartment`.

    If both are None the query is unfiltered (global overview).
    
    Note: With the new structure, each site has ONE meter (block-level).
    Apartment stats are derived from bills distributed by occupancy.
    """
    today = timezone.now().date()

    qs_summary = ConsumptionSummary.objects.filter(period_type='day', period_date=today)
    qs_meters = Meter.objects.all()
    qs_bills = Bill.objects.all()
    qs_payments = Payment.objects.all()

    if apartment is not None:
        # For apartments: get the site's summary (since meter is at site level)
        qs_summary = qs_summary.filter(site=apartment.site)
        qs_meters = qs_meters.filter(site=apartment.site)
        qs_bills = qs_bills.filter(apartment=apartment)
        qs_payments = qs_payments.filter(bill__apartment=apartment)
    elif site is not None:
        qs_summary = qs_summary.filter(site=site)
        qs_meters = qs_meters.filter(site=site)
        qs_bills = qs_bills.filter(site=site)
        qs_payments = qs_payments.filter(bill__site=site)

    total_vol = float(qs_summary.aggregate(Sum('total_volume')).get('total_volume__sum') or 0)
    total_vol_all = float(qs_bills.aggregate(Sum('volume_consumed')).get('volume_consumed__sum') or 0)

    # If calculating for an apartment, get its proportional share of consumption
    if apartment is not None:
        site_apartments = Apartment.objects.filter(site=apartment.site)
        total_occupants = site_apartments.aggregate(Sum('occupants')).get('occupants__sum') or 0
        if total_occupants > 0:
            total_vol = total_vol * (apartment.occupants / total_occupants)
        else:
            total_vol = 0

    active_meters = qs_meters.filter(status='active').count()
    total_due = qs_bills.aggregate(Sum('total_bill')).get('total_bill__sum') or Decimal('0')
    total_paid = qs_payments.aggregate(Sum('amount')).get('amount__sum') or Decimal('0')
    outstanding_bills_amount = total_due - total_paid
    collection_rate = int((total_paid * 100) / total_due) if total_due else 0
    outstanding_bills_qs = _get_bills_for_outstanding_calculation(qs_bills)
    outstanding_bills_count = 0
    outstanding_bills_consumption = Decimal('0')
    for bill in outstanding_bills_qs:
        if bill.balance > Decimal('0'):
            outstanding_bills_count += 1
            outstanding_bills_consumption += bill.volume_consumed or Decimal('0')

    two_places = Decimal('0.01')
    outstanding_bills_amount = max(outstanding_bills_amount, Decimal('0'))

    return {
        'total_consumption_m3': float(round(total_vol, 2)),
        'total_consumption_all_time': float(round(total_vol_all, 2)),
        'active_meters': active_meters,
        'outstanding_bills': outstanding_bills_amount.quantize(two_places, rounding=ROUND_HALF_UP),
        'outstanding_bills_count': outstanding_bills_count,
        'collection_rate': int(collection_rate),
        'total_due': total_due.quantize(two_places, rounding=ROUND_HALF_UP),
        'total_paid': total_paid.quantize(two_places, rounding=ROUND_HALF_UP),
        'outstanding_bills_consumption': float(round(outstanding_bills_consumption, 2)),
    }


def home_dashboard(request):
    """Route to role-specific dashboard based on user role."""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url='accounts:login')

    role = getattr(request.user, 'role', 'user')

    if role == 'superuser' or request.user.is_superuser:
        return superuser_dashboard(request)
    elif role == 'block_admin':
        return block_admin_dashboard(request)
    else:
        return user_dashboard(request)


def superuser_dashboard(request):
    """Dashboard for superusers showing global overview and all blocks/apartments."""
    stats = _gather_stats()

    # get all sites and apartments
    sites = Site.objects.all().count()
    apartments = Apartment.objects.all().count()
    meters = Meter.objects.all().count()
    total_users = Site.objects.filter(user__isnull=False).count()

    # recent bills
    recent_bills = Bill.objects.select_related('site', 'apartment', 'apartment__user').order_by('-issued_at')[:10]
    for bill in recent_bills:
        _apply_bill_payment_status(bill, save=True)

    context = {
        'title': 'Superuser Dashboard — Voltaqua',
        'stats': stats,
        'entity_name': 'Global Overview',
        'dashboard_type': 'superuser',
        'total_sites': sites,
        'total_apartments': apartments,
        'total_meters': meters,
        'total_admins': total_users,
        'recent_bills': recent_bills,
    }
    return render(request, 'water/superuser_dashboard.html', context)


def block_admin_dashboard(request):
    """Dashboard for block admins showing their assigned block and apartments."""
    # get the user's assigned site
    try:
        site = Site.objects.get(user=request.user)
    except Site.DoesNotExist:
        return redirect('water:create-site')

    if not Meter.objects.filter(site=site).exists():
        return redirect('water:create-meter')

    stats = _gather_stats(site=site)

    # get apartments in their block
    apartments = Apartment.objects.filter(site=site).select_related('user')
    apartment_data = []
    for apt in apartments:
        apt_stats = _gather_stats(apartment=apt)
        apartment_data.append({
            'apartment': apt,
            'stats': apt_stats,
        })

    # bills for this block
    recent_bills = Bill.objects.filter(site=site).select_related('apartment', 'apartment__user').order_by('-issued_at')[:10]
    for bill in recent_bills:
        _apply_bill_payment_status(bill, save=True)

    context = {
        'title': f'Block {site.code} Dashboard',
        'stats': stats,
        'entity_name': f'Block {site.name}',
        'dashboard_type': 'block_admin',
        'site': site,
        'apartments': apartment_data,
        'total_apartments': len(apartments),
        'recent_bills': recent_bills,
    }
    return render(request, 'water/block_admin_dashboard.html', context)


def user_dashboard(request):
    """Dashboard for regular users (residents) showing their apartment data."""
    
    # Find the apartment assigned to this user
    apartment = Apartment.objects.filter(user=request.user).first()
    
    if apartment:
        stats = _gather_stats(apartment=apartment)
        context = {
            'title': f'My Dashboard — Apt {apartment.number}',
            'stats': stats,
            'entity_name': f'My Apartment ({apartment.number})',
            'dashboard_type': 'user',
            'apartment': apartment,
        }
        return render(request, 'water/apartment_details.html', context)

    return redirect('water:join-site')


def block_dashboard(request, site_id):
    """Dashboard scoped to a single block (Site).

    Only superusers and the assigned block admin can access.
    """
    try:
        site = Site.objects.get(pk=site_id)
    except Site.DoesNotExist:
        raise Http404

    if not _can_view_site(request.user, site):
        raise Http404

    stats = _gather_stats(site=site)

    # get apartments in their block
    apartments = Apartment.objects.filter(site=site).select_related('user')
    apartment_data = []
    for apt in apartments:
        apt_stats = _gather_stats(apartment=apt)
        apartment_data.append({
            'apartment': apt,
            'stats': apt_stats,
        })

    # bills for this block
    recent_bills = Bill.objects.filter(site=site).select_related('apartment', 'apartment__user').order_by('-issued_at')[:10]
    for bill in recent_bills:
        _apply_bill_payment_status(bill, save=True)

    context = {
        'title': f'Block {site.code} Dashboard',
        'stats': stats,
        'entity_name': f'Block {site.name}',
        'dashboard_type': 'block_admin',
        'site': site,
        'apartments': apartment_data,
        'total_apartments': len(apartments),
        'recent_bills': recent_bills,
    }
    return render(request, 'water/block_admin_dashboard.html', context)


def apartment_dashboard(request, apartment_id):
    """Dashboard scoped to a single apartment.

    Only superusers and the assigned block admin (of the parent site) can access.
    """
    try:
        apt = Apartment.objects.get(pk=apartment_id)
    except Apartment.DoesNotExist:
        raise Http404

    if not _can_view_apartment(request.user, apt):
        raise Http404

    stats = _gather_stats(apartment=apt)
    context = {
        'title': f'Apt {apt.number} — Water Dashboard',
        'stats': stats,
        'entity_name': f'{apt}',
        'dashboard_type': 'apartment_view',
        'apartment': apt,
    }
    return render(request, 'water/apartment_details.html', context)


def sites_list(request):
    """Superuser view: List all blocks (sites)."""
    if request.user.role != 'superuser':
        raise Http404

    sites = Site.objects.all().prefetch_related('apartments', 'meters')
    
    site_data = []
    for site in sites:
        stats = _gather_stats(site=site)
        site_data.append({
            'site': site,
            'apartment_count': site.apartments.count(),
            'meter_count': site.meters.count(),
            'stats': stats,
        })
    
    context = {
        'title': 'All Blocks — Voltaqua',
        'site_data': site_data,
        'total_sites': len(site_data),
    }
    return render(request, 'water/sites_list.html', context)


def apartments_list(request):
    """Superuser view: List all apartments."""
    if request.user.role != 'superuser':
        raise Http404

    apartments = Apartment.objects.select_related('site', 'user').all()
    
    apt_data = []
    for apt in apartments:
        stats = _gather_stats(apartment=apt)
        apt_data.append({
            'apartment': apt,
            'stats': stats,
        })
    
    context = {
        'title': 'All Apartments — Voltaqua',
        'apartment_data': apt_data,
        'total_apartments': len(apt_data),
    }
    return render(request, 'water/apartments_list.html', context)


def meters_list(request):
    """Superuser view: List all meters."""
    if request.user.role != 'superuser':
        raise Http404

    meters = Meter.objects.select_related('site', 'apartment').all()
    
    meter_data = []
    for meter in meters:
        meter_data.append({
            'meter': meter,
            'apartment': meter.apartment,
            'site': meter.site,
        })
    
    context = {
        'title': 'All Meters — Voltaqua',
        'meter_data': meter_data,
        'total_meters': len(meter_data),
    }
    return render(request, 'water/meters_list.html', context)


def admins_list(request):
    """Superuser view: List all block admin users."""
    if request.user.role != 'superuser':
        raise Http404

    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    admins = User.objects.filter(role='block_admin')
    
    admin_data = []
    for admin in admins:
        assigned_site = Site.objects.filter(user=admin).first()
        apartments = Apartment.objects.filter(site__user=admin).count() if assigned_site else 0
        meters = Meter.objects.filter(site__user=admin).count() if assigned_site else 0
        
        admin_data.append({
            'admin': admin,
            'site': assigned_site,
            'apartment_count': apartments,
            'meter_count': meters,
        })
    
    context = {
        'title': 'Block Administrators — Voltaqua',
        'admin_data': admin_data,
        'total_admins': len(admin_data),
    }
    return render(request, 'water/admins_list.html', context)


@login_required
def manage_users(request):
    """Superuser view: List all users and manage their roles."""
    if request.user.role != 'superuser':
        raise Http404

    User = get_user_model()

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('role')
        
        user_obj = get_object_or_404(User, pk=user_id)
        
        # Prevent changing own role to avoid locking out
        if user_obj == request.user:
            messages.error(request, "You cannot change your own role.")
        elif new_role in dict(User.USER_ROLE_CHOICES):
            user_obj.role = new_role
            # Update permissions based on role
            user_obj.is_superuser = (new_role == 'superuser')
            user_obj.is_staff = (new_role == 'superuser')
            user_obj.save()
            messages.success(request, f"Role for {user_obj.email} updated to {user_obj.get_role_display()}.")
        else:
            messages.error(request, "Invalid role selected.")
        return redirect('water:manage-users')

    users = User.objects.all().order_by('-date_joined')
    context = {
        'title': 'Manage Users — Voltaqua',
        'users': users,
        'roles': User.USER_ROLE_CHOICES,
    }
    return render(request, 'water/manage_users.html', context)


@login_required
def edit_apartment(request, apartment_id):
    """Edit apartment occupants (block admin only)."""
    apartment = get_object_or_404(Apartment, pk=apartment_id)
    site = apartment.site
    
    # Check if user is the block admin for this site or a superuser
    if not (request.user.role == 'superuser' or (request.user.role == 'block_admin' and site.user_id == request.user.id)):
        raise Http404
    
    if request.method == 'POST':
        form = ApartmentForm(request.POST, instance=apartment)
        if form.is_valid():
            form.save()
            messages.success(request, f'Apartment {apartment.number} updated successfully.')
            return redirect('water:block-dashboard', site_id=site.id)
    else:
        form = ApartmentForm(instance=apartment)
    
    context = {
        'title': f'Edit Apartment {apartment.number}',
        'form': form,
        'apartment': apartment,
        'site': site,
    }
    return render(request, 'water/edit_apartment.html', context)


@login_required
def enter_bill(request, site_id):
    """Enter monthly bill for a block (block admin only).

    The form now allows the block admin to specify the number of occupants for
    each apartment for the billing period.  These values are saved in
    ``BillOccupancy`` records and also update the apartment's permanent
    ``occupants`` field for convenience.
    """
    site = get_object_or_404(Site, pk=site_id)
    
    # Check if user is the block admin for this site
    if request.user.role != 'block_admin' or site.user_id != request.user.id:
        raise Http404
    
    apartments = Apartment.objects.filter(site=site)
    # build initial occupancy map for GET or error re-rendering
    occupancies = {apt.id: apt.occupants for apt in apartments}
    total_occupants = sum(occupancies.values())
    # helper list used in template, includes the value that will be editable
    def make_data():
        return [
            {'apt': apt, 'occupants': occupancies.get(apt.id, apt.occupants)}
            for apt in apartments
        ]
    apt_data = make_data()

    if request.method == 'POST':
        form = BillEntryForm(site=site, data=request.POST)
        # parse occupancy overrides
        valid_occupancy = True
        parsed = {}
        for apt in apartments:
            key = f"occupants_{apt.id}"
            val = request.POST.get(key)
            if val is None or val == '':
                # fall back to existing number if not provided
                parsed[apt.id] = apt.occupants
            else:
                try:
                    num = int(val)
                    if num < 0:
                        raise ValueError
                    parsed[apt.id] = num
                except ValueError:
                    form.add_error(None, f"Invalid occupant count for apartment {apt.number}.")
                    valid_occupancy = False
        if parsed:
            total_occupants = sum(parsed.values())
        # update occupancy map for context if re-rendering
        occupancies = parsed or occupancies

        if form.is_valid() and valid_occupancy:
            period_start = form.cleaned_data['period_start']
            period_end = form.cleaned_data['period_end']
            water_bill = form.cleaned_data['water_bill']
            dustbin_bill = form.cleaned_data['dustbin_bill']
            total_volume = form.cleaned_data.get('total_volume')

            active_apartments = apartments.filter(is_active=True)
            num_active_apartments = active_apartments.count()

            if active_apartments.exists():
                dustbin_bill_per_apartment = (
                    Decimal(dustbin_bill) / Decimal(num_active_apartments)
                    if num_active_apartments > 0
                    else Decimal(0)
                )

                if total_occupants > 0:
                    created_bills = []
                    for apartment in active_apartments:
                        occ = occupancies.get(apartment.id, apartment.occupants)
                        apartment_water_share = (Decimal(occ) / Decimal(total_occupants)) * water_bill
                        volume_share = (Decimal(occ) / Decimal(total_occupants)) * total_volume if total_volume else 0
                        total_bill = apartment_water_share + dustbin_bill_per_apartment

                        bill = Bill.objects.create(
                            user=request.user,
                            site=site,
                            apartment=apartment,
                            period_start=period_start,
                            period_end=period_end,
                            total_bill=round(total_bill, 2),
                            water_bill=round(apartment_water_share, 2),
                            dustbin_bill=round(dustbin_bill_per_apartment, 2),
                            volume_consumed=round(volume_share, 2),
                            status='pending',
                            due_at=timezone.now() + timedelta(days=30),
                        )
                        BillOccupancy.objects.create(
                            bill=bill,
                            apartment=apartment,
                            occupants=occ,
                        )
                        if apartment.occupants != occ:
                            apartment.occupants = occ
                            apartment.save(update_fields=['occupants'])

                        created_bills.append(bill)

                        DustbinBill.objects.create(
                            bill=bill,
                            apartment=apartment,
                            amount=round(dustbin_bill_per_apartment, 2),
                            period_start=period_start,
                            period_end=period_end,
                        )
                    
                    messages.success(
                        request,
                        f'Bills created successfully! {len(created_bills)} bills distributed to apartments.'
                    )
                    return redirect('water:block-dashboard', site_id=site.id)
                else:
                    messages.error(request, 'No occupants recorded for any apartments. Please update apartment occupancy first.')
            else:
                messages.error(request, 'No active apartments found in this block.')
    else:
        form = BillEntryForm(site=site)
    
    context = {
        'title': f'Enter Monthly Bill — {site.name}',
        'form': form,
        'site': site,
        'apartments': apartments,
        'apt_data': apt_data,
        'total_occupants': total_occupants,
    }
    return render(request, 'water/enter_bill.html', context)


@login_required
def record_payment(request, bill_id):
    """Record a payment for a specific bill (block admin only)."""
    bill = get_object_or_404(Bill, pk=bill_id)
    
    # Check permissions: must be the block admin of the site. Superusers cannot record payments.
    if not (request.user.role == 'block_admin' and bill.site.user_id == request.user.id):
        raise Http404

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.bill = bill
            payment.paid_at = timezone.now()
            payment.save()

            total_paid = bill.payments.aggregate(Sum('amount')).get('amount__sum') or Decimal('0')
            _apply_bill_payment_status(bill, total_paid=total_paid, save=True)
            
            messages.success(request, f'Payment of {payment.amount} recorded successfully.')
            return redirect('water:block-dashboard', site_id=bill.site.id)
    else:
        # Default to remaining amount
        total_paid = bill.payments.aggregate(Sum('amount')).get('amount__sum') or 0
        remaining = max(0, bill.total_bill - total_paid)
        form = PaymentForm(initial={'amount': remaining, 'method': 'cash'})

    context = {
        'title': f'Record Payment - Bill #{bill.id}',
        'form': form,
        'bill': bill,
    }
    return render(request, 'water/record_payment.html', context)


@login_required
def apartment_payment_history(request, apartment_id):
    """Show payment history for a specific apartment."""
    apartment = get_object_or_404(Apartment, pk=apartment_id)

    # Check permissions
    if not _can_view_apartment(request.user, apartment):
        raise Http404

    # Get all years with payments for this apartment
    payment_years = Payment.objects.filter(bill__apartment=apartment).dates('paid_at', 'year', order='DESC')
    
    # Get selected year from query params, default to the latest year if available
    selected_year_str = request.GET.get('year')
    selected_year = None

    if selected_year_str:
        try:
            selected_year = int(selected_year_str)
        except (ValueError, TypeError):
            selected_year = None # Or handle error
    elif payment_years:
        selected_year = payment_years[0].year
    
    if selected_year:
        payments = Payment.objects.filter(
            bill__apartment=apartment, 
            paid_at__year=selected_year
        ).select_related('bill').order_by('-paid_at')
    else:
        payments = Payment.objects.none()

    context = {
        'title': f'Payment History - Apt {apartment.number}',
        'apartment': apartment,
        'payments': payments,
        'payment_years': payment_years,
        'selected_year': selected_year,
    }
    return render(request, 'water/payment_history.html', context)


@login_required
def apartment_bill_list(request, apartment_id):
    """Show a detailed list of all bills for a specific apartment."""
    apartment = get_object_or_404(Apartment, pk=apartment_id)

    # Check permissions
    if not _can_view_apartment(request.user, apartment):
        raise Http404

    # Get all bills for the apartment, with payment sums annotated
    bills_qs = Bill.objects.filter(apartment=apartment).annotate(
        total_paid=Coalesce(Sum('payments__amount'), 0, output_field=models.DecimalField())
    ).order_by('period_end', 'issued_at', 'id')

    bills = _settle_bills_with_carryover(list(bills_qs), save=True)
    bills.reverse()

    context = {
        'title': f'Bill History - Apt {apartment.number}',
        'apartment': apartment,
        'bills': bills,
    }
    return render(request, 'water/bill_history.html', context)


@login_required
def create_site(request):
    """Onboarding: Allow a block admin to register their block details."""
    if request.user.role != 'block_admin':
        return redirect('water:home')
    
    # If already has a site, go to dashboard
    if Site.objects.filter(user=request.user).exists():
        return redirect('water:dashboard')

    if request.method == 'POST':
        name = request.POST.get('name')
        code = request.POST.get('code')
        address = request.POST.get('address')
        
        if not name or not code:
            messages.error(request, "Block Name and Site Code are required.")
        elif Site.objects.filter(code=code).exists():
            messages.error(request, "This Site Code is already taken. Please choose another.")
        else:
            Site.objects.create(
                user=request.user,
                name=name,
                code=code,
                address=address
            )
            messages.success(request, "Block registered successfully! You can now add apartments.")
            return redirect('water:dashboard')
    
    return render(request, 'water/create_site.html', {'title': 'Register Your Block'})


@login_required
def create_meter(request):
    """Onboarding: Allow a block admin to register a meter for their block."""
    if request.user.role != 'block_admin':
        return redirect('water:home')
    
    try:
        site = Site.objects.get(user=request.user)
    except Site.DoesNotExist:
        return redirect('water:create-site')

    # If already has a meter, go to dashboard
    if Meter.objects.filter(site=site).exists():
        return redirect('water:dashboard')

    if request.method == 'POST':
        serial_number = request.POST.get('serial_number')
        model = request.POST.get('model')
        
        if not serial_number:
            messages.error(request, "Serial Number is required.")
        elif Meter.objects.filter(serial_number=serial_number).exists():
            messages.error(request, "This Serial Number is already registered.")
        else:
            Meter.objects.create(
                site=site,
                serial_number=serial_number,
                model=model,
                status='active',
                installed_at=timezone.now()
            )
            messages.success(request, "Meter registered successfully!")
            return redirect('water:dashboard')
    
    return render(request, 'water/create_meter.html', {'title': 'Register Block Meter'})


@login_required
def join_site(request):
    """Onboarding: Allow a resident to join a block using a site code."""
    if request.user.role != 'user':
        return redirect('water:home')
        
    # If already has an apartment, go to dashboard
    if Apartment.objects.filter(user=request.user).exists():
        return redirect('water:dashboard')

    if request.method == 'POST':
        site_code = request.POST.get('site_code')
        apt_number = request.POST.get('apt_number')
        
        if not site_code or not apt_number:
            messages.error(request, "Site Code and Apartment Number are required.")
        else:
            try:
                site = Site.objects.get(code=site_code)
                # Check if apartment exists, or create it if it doesn't
                # This allows for smoother onboarding where residents can "claim" their spot
                apartment, created = Apartment.objects.get_or_create(
                    site=site, 
                    number=apt_number,
                    defaults={'occupants': 1}
                )
                
                if apartment.user and apartment.user != request.user:
                    messages.error(request, f"Apartment {apt_number} is already claimed by another user.")
                else:
                    apartment.user = request.user
                    apartment.save()
                    messages.success(request, f"Successfully joined {site.name}!")
                    return redirect('water:dashboard')
                    
            except Site.DoesNotExist:
                messages.error(request, "Invalid Site Code. Please ask your Block Admin for the correct code.")
            
    return render(request, 'water/join_site.html', {'title': 'Join Your Block'})
