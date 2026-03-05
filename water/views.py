from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.utils import timezone
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import timedelta

from .models import (
    Site,
    Apartment,
    Meter,
    Reading,
    ConsumptionSummary,
    Bill,
    BillOccupancy,
    Payment,
)
from .forms import ApartmentForm, BillEntryForm


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
    - Regular users cannot currently view apartment dashboards.
    """
    if user.role == 'superuser':
        return True
    if user.role == 'block_admin' and apartment.site.user_id == user.id:
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

    total_vol = qs_summary.aggregate(Sum('total_volume')).get('total_volume__sum') or 0
    active_meters = qs_meters.filter(status='active').count()
    outstanding_bills = qs_bills.filter(status__in=['pending', 'overdue']).count()
    total_due = qs_bills.aggregate(Sum('amount_due')).get('amount_due__sum') or 0
    total_paid = qs_payments.aggregate(Sum('amount')).get('amount__sum') or 0
    collection_rate = int((total_paid / total_due) * 100) if total_due else 0

    return {
        'total_consumption_m3': float(round(total_vol, 2)),
        'active_meters': active_meters,
        'outstanding_bills': outstanding_bills,
        'collection_rate': int(collection_rate),
    }


def _gather_latest_readings(site=None, apartment=None, limit=5):
    """Gather latest meter readings.
    
    With the new structure:
    - Site readings come from the site's block-level meter
    - Apartment readings show the block meter (since billing is proportional by occupancy)
    """
    qs = Reading.objects.select_related('meter', 'meter__site')
    
    if apartment is not None:
        # Show readings from the apartment's site meter (block-level)
        qs = qs.filter(meter__site=apartment.site)
    elif site is not None:
        qs = qs.filter(meter__site=site)
    
    qs = qs.order_by('-timestamp')[:limit]

    readings = []
    rate_per_m3 = 1.5
    for r in qs:
        consumption = float(r.value)
        bill_amount = consumption * rate_per_m3
        readings.append({
            'apartment': r.meter.apartment.number if r.meter.apartment else (r.meter.site.name if r.meter.site else r.meter.serial_number),
            'meter_id': r.meter.serial_number,
            'consumption': float(round(consumption, 2)),
            'bill': float(round(bill_amount, 2)),
            'status': 'Paid' if Payment.objects.filter(bill__site=r.meter.site).exists() else 'Unpaid',
        })
    return readings


def home_dashboard(request):
    """Route to role-specific dashboard based on user role."""
    if not request.user.is_authenticated:
        return render(request, 'login.html')

    role = getattr(request.user, 'role', 'user')

    if role == 'superuser':
        return superuser_dashboard(request)
    elif role == 'block_admin':
        return block_admin_dashboard(request)
    else:
        return user_dashboard(request)


def superuser_dashboard(request):
    """Dashboard for superusers showing global overview and all blocks/apartments."""
    stats = _gather_stats()
    latest_readings = _gather_latest_readings(limit=10)

    # get all sites and apartments
    sites = Site.objects.all().count()
    apartments = Apartment.objects.all().count()
    meters = Meter.objects.all().count()
    total_users = Site.objects.filter(user__isnull=False).count()

    # recent bills
    recent_bills = Bill.objects.select_related('site', 'apartment').order_by('-issued_at')[:10]

    context = {
        'title': 'Superuser Dashboard — Voltaqua',
        'stats': stats,
        'latest_readings': latest_readings,
        'entity_name': 'Global Overview',
        'dashboard_type': 'superuser',
        'total_sites': sites,
        'total_apartments': apartments,
        'total_meters': meters,
        'total_admins': total_users,
        'recent_bills': recent_bills,
    }
    return render(request, 'superuser_dashboard.html', context)


def block_admin_dashboard(request):
    """Dashboard for block admins showing their assigned block and apartments."""
    # get the user's assigned site
    try:
        site = Site.objects.get(user=request.user)
    except Site.DoesNotExist:
        context = {
            'title': 'Block Admin Dashboard',
            'message': 'No block assigned to your account.',
            'dashboard_type': 'block_admin',
        }
        return render(request, 'block_admin_dashboard.html', context)

    stats = _gather_stats(site=site)
    latest_readings = _gather_latest_readings(site=site, limit=10)

    # get apartments in their block
    apartments = Apartment.objects.filter(site=site)
    apartment_data = []
    for apt in apartments:
        apt_stats = _gather_stats(apartment=apt)
        apartment_data.append({
            'apartment': apt,
            'stats': apt_stats,
        })

    # bills for this block
    recent_bills = Bill.objects.filter(site=site).select_related('apartment').order_by('-issued_at')[:10]

    context = {
        'title': f'Block {site.code} Dashboard',
        'stats': stats,
        'latest_readings': latest_readings,
        'entity_name': f'Block {site.name}',
        'dashboard_type': 'block_admin',
        'site': site,
        'apartments': apartment_data,
        'total_apartments': len(apartments),
        'recent_bills': recent_bills,
    }
    return render(request, 'block_admin_dashboard.html', context)


def user_dashboard(request):
    """Dashboard for regular users (residents) showing their apartment data."""
    # for now, show a simple user dashboard
    # in the future, link users to apartments
    context = {
        'title': 'My Dashboard — Voltaqua',
        'entity_name': 'My Apartment',
        'dashboard_type': 'user',
        'message': 'View your water consumption and billing information here.',
    }
    return render(request, 'user_dashboard.html', context)


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
    latest_readings = _gather_latest_readings(site=site)

    # get apartments in their block
    apartments = Apartment.objects.filter(site=site)
    apartment_data = []
    for apt in apartments:
        apt_stats = _gather_stats(apartment=apt)
        apartment_data.append({
            'apartment': apt,
            'stats': apt_stats,
        })

    # bills for this block
    recent_bills = Bill.objects.filter(site=site).select_related('apartment').order_by('-issued_at')[:10]

    context = {
        'title': f'Block {site.code} Dashboard',
        'stats': stats,
        'latest_readings': latest_readings,
        'entity_name': f'Block {site.name}',
        'dashboard_type': 'block_admin',
        'site': site,
        'apartments': apartment_data,
        'total_apartments': len(apartments),
        'recent_bills': recent_bills,
    }
    return render(request, 'block_admin_dashboard.html', context)


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
    latest_readings = _gather_latest_readings(apartment=apt)
    context = {
        'title': f'Apt {apt.number} — Water Dashboard',
        'stats': stats,
        'latest_readings': latest_readings,
        'entity_name': f'{apt}',
        'dashboard_type': 'apartment_view',
        'apartment': apt,
    }
    return render(request, 'apartment_details.html', context)


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
    return render(request, 'sites_list.html', context)


def apartments_list(request):
    """Superuser view: List all apartments."""
    if request.user.role != 'superuser':
        raise Http404

    apartments = Apartment.objects.select_related('site').all()
    
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
    return render(request, 'apartments_list.html', context)


def meters_list(request):
    """Superuser view: List all meters."""
    if request.user.role != 'superuser':
        raise Http404

    meters = Meter.objects.select_related('site', 'apartment').all()
    
    meter_data = []
    for meter in meters:
        latest_reading = Reading.objects.filter(meter=meter).order_by('-timestamp').first()
        meter_data.append({
            'meter': meter,
            'latest_reading': latest_reading,
            'apartment': meter.apartment,
            'site': meter.site,
        })
    
    context = {
        'title': 'All Meters — Voltaqua',
        'meter_data': meter_data,
        'total_meters': len(meter_data),
    }
    return render(request, 'meters_list.html', context)


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
    return render(request, 'admins_list.html', context)


@login_required
def edit_apartment(request, apartment_id):
    """Edit apartment occupants (block admin only)."""
    apartment = get_object_or_404(Apartment, pk=apartment_id)
    site = apartment.site
    
    # Check if user is the block admin for this site
    if request.user.role != 'block_admin' or site.user_id != request.user.id:
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
    return render(request, 'edit_apartment.html', context)


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
            total_amount = form.cleaned_data['total_amount']
            total_volume = form.cleaned_data.get('total_volume')
            
            if apartments.exists():
                if total_occupants > 0:
                    created_bills = []
                    for apartment in apartments:
                        occ = occupancies.get(apartment.id, apartment.occupants)
                        apartment_share = (occ / total_occupants) * total_amount
                        volume_share = (occ / total_occupants) * total_volume if total_volume else 0

                        bill = Bill.objects.create(
                            user=request.user,
                            site=site,
                            apartment=apartment,
                            period_start=period_start,
                            period_end=period_end,
                            amount_due=round(apartment_share, 2),
                            status='pending',
                            due_at=timezone.now() + timedelta(days=30),
                        )
                        # record which occupancy was used
                        BillOccupancy.objects.create(
                            bill=bill,
                            apartment=apartment,
                            occupants=occ,
                        )
                        # update apartment for future default
                        if apartment.occupants != occ:
                            apartment.occupants = occ
                            apartment.save(update_fields=['occupants'])
                        created_bills.append(bill)
                    
                    messages.success(
                        request,
                        f'Bills created successfully! {len(created_bills)} bills distributed to apartments based on occupancy.'
                    )
                    return redirect('water:block-dashboard', site_id=site.id)
                else:
                    messages.error(request, 'No occupants recorded for any apartments. Please update apartment occupancy first.')
            else:
                messages.error(request, 'No apartments found in this block.')
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
    return render(request, 'enter_bill.html', context)
