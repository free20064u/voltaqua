from django.core.management.base import BaseCommand
from faker import Faker
from django.utils import timezone
import random
import uuid

from water.models import (
    Site, Apartment, Meter, Sensor, Reading, Alert, ConsumptionSummary,
    Tariff, Bill, Payment, Maintenance, DeviceHealth, Notification
)
from django.contrib.auth import get_user_model

faker = Faker()


def create_users(num_superusers=1, num_block_admins=5, num_residents=15):
    """Create users with different roles."""
    User = get_user_model()
    users = {'superuser': [], 'block_admin': [], 'user': []}
    
    # Create superusers
    for _ in range(num_superusers):
        user = User.objects.create_user(
            email=faker.unique.email(),
            password='password123',
            first_name=faker.first_name(),
            last_name=faker.last_name(),
            role='superuser',
            is_staff=True,
            is_superuser=True,
        )
        users['superuser'].append(user)
    
    # Create block admins
    for _ in range(num_block_admins):
        user = User.objects.create_user(
            email=faker.unique.email(),
            password='password123',
            first_name=faker.first_name(),
            last_name=faker.last_name(),
            role='block_admin',
            is_staff=False,
            is_superuser=False,
        )
        users['block_admin'].append(user)
    
    # Create residents/users
    for _ in range(num_residents):
        user = User.objects.create_user(
            email=faker.unique.email(),
            password='password123',
            first_name=faker.first_name(),
            last_name=faker.last_name(),
            role='user',
            is_staff=False,
            is_superuser=False,
        )
        users['user'].append(user)
    
    return users


def create_sites(block_admin_users, n=5):
    """Create sites linked to block admin users."""
    sites = []
    for i, admin in enumerate(block_admin_users[:n]):
        # Generate unique site code using UUID to guarantee uniqueness
        unique_code = f"SITE-{uuid.uuid4().hex[:8].upper()}"
        site = Site.objects.create(
            name=faker.company(),
            code=unique_code,
            address=faker.address(),
            latitude=faker.latitude(),
            longitude=faker.longitude(),
            timezone=faker.timezone(),
            user=admin,  # Link to block admin
        )
        sites.append(site)
    return sites


def create_apartments(sites, per_site=4):
    """Create apartments within each site."""
    apartments = []
    for site in sites:
        for unit_num in range(1, per_site + 1):
            apartment = Apartment.objects.create(
                site=site,
                number=f'{unit_num:02d}',
                occupants=random.randint(1, 6),
            )
            apartments.append(apartment)
    return apartments


def create_meters(sites, apartments, per_site=1):
    """Create one meter per site (block) for the entire block."""
    meters = []
    meter_counter = 1000
    for site in sites:
        # Create ONE meter per site, not linked to any apartment
        meter = Meter.objects.create(
            site=site,
            apartment=None,  # Block-level meter, not apartment-specific
            serial_number=f'MTR-{meter_counter:08d}',
            model=faker.word().upper(),
            installed_at=faker.date_time_between(start_date='-2y', end_date='now', tzinfo=timezone.get_current_timezone()),
            status='active',  # Block meters should be active
        )
        meters.append(meter)
        meter_counter += 1
    return meters


def create_sensors(meters, per_meter=2):
    sensors = []
    types = [t.value for t in Sensor.SensorType]
    for meter in meters:
        for _ in range(per_meter):
            sensor = Sensor.objects.create(
                meter=meter,
                sensor_type=random.choice(types),
                unit=random.choice(['m3/h', 'L/s', 'ppm', '%']),
                installed_at=faker.date_time_between(start_date=meter.installed_at, end_date='now', tzinfo=timezone.get_current_timezone()),
            )
            sensors.append(sensor)
    return sensors


def create_readings(sensors, count=1000):
    readings = []
    for sensor in sensors:
        for _ in range(count):
            ts = faker.date_time_between(start_date='-1y', end_date='now', tzinfo=timezone.get_current_timezone())
            readings.append(
                Reading(
                    sensor=sensor,
                    meter=sensor.meter,
                    timestamp=ts,
                    value=round(random.uniform(0, 100), 6),
                    quality=random.choice(['ok','suspect']),
                )
            )
    Reading.objects.bulk_create(readings)


def create_alerts(sites, count=20):
    alerts = []
    for _ in range(count):
        site = random.choice(sites)
        a = Alert.objects.create(
            site=site,
            alert_type=random.choice(['leak','outage','high_flow','low_flow','sensor_error']),
            severity=random.choice(['low','medium','high','critical']),
            message=faker.sentence(),
            first_seen=faker.date_time_between(start_date='-1y', end_date='now', tzinfo=timezone.get_current_timezone()),
            last_seen=timezone.now(),
            status=random.choice(['open','ack','closed']),
        )
        alerts.append(a)
    return alerts


def create_summaries(meters):
    # make a few daily summaries per meter
    for meter in meters:
        for i in range(30):
            day = timezone.now().date() - timezone.timedelta(days=i)
            ConsumptionSummary.objects.create(
                period_date=day,
                period_type='day',
                meter=meter,
                site=meter.site,
                total_volume=round(random.uniform(100, 1000), 6),
                avg_flow=round(random.uniform(1, 10), 6),
                min_flow=round(random.uniform(0, 1), 6),
                max_flow=round(random.uniform(10, 20), 6),
            )


def create_bills(users_dict, sites, apartments, count=30):
    """Create block-level bills and distribute to apartments based on occupancy."""
    bills = []
    
    # Create bills for each block (site)
    admin_users = users_dict['block_admin']
    for admin in admin_users:
        admin_sites = Site.objects.filter(user=admin)
        for site in admin_sites:
            for _ in range(count // max(len(admin_users), 1)):
                start = faker.date_between(start_date='-6M', end_date='-1M')
                end = start + timezone.timedelta(days=30)
                
                # Create ONE bill for the entire block
                total_block_amount = round(random.uniform(200, 1000), 2)
                
                # Get all apartments in the site
                site_apartments = site.apartments.all()
                if site_apartments.exists():
                    # Calculate total occupants in the block
                    total_occupants = sum(apt.occupants for apt in site_apartments)
                    
                    # Create a bill for each apartment, distributed by occupancy
                    if total_occupants > 0:
                        for apartment in site_apartments:
                            # Distribute the bill proportionally based on occupants
                            apartment_share = (apartment.occupants / total_occupants) * total_block_amount
                            apartment_bill = Bill.objects.create(
                                user=admin,
                                site=site,
                                apartment=apartment,
                                period_start=start,
                                period_end=end,
                                amount_due=round(apartment_share, 2),
                                status=random.choice(['pending', 'paid', 'overdue']),
                                due_at=timezone.now() + timezone.timedelta(days=30),
                            )
                            bills.append(apartment_bill)
                else:
                    # If no apartments, create a site-level bill
                    bill = Bill.objects.create(
                        user=admin,
                        site=site,
                        apartment=None,
                        period_start=start,
                        period_end=end,
                        amount_due=total_block_amount,
                        status=random.choice(['pending', 'paid', 'overdue']),
                        due_at=timezone.now() + timezone.timedelta(days=30),
                    )
                    bills.append(bill)
    
    return bills


def create_payments(bills):
    for bill in bills:
        if bill.status == 'paid':
            Payment.objects.create(
                bill=bill,
                amount=bill.amount_due,
                paid_at=bill.due_at - timezone.timedelta(days=random.randint(1,10)),
                method=random.choice(['credit_card','bank_transfer','cash']),
                reference=faker.uuid4(),
            )


def create_maintenance(meters, count=20):
    for _ in range(count):
        meter = random.choice(meters)
        Maintenance.objects.create(
            meter=meter,
            site=meter.site,
            scheduled_at=faker.date_time_between(start_date='-1y', end_date='now', tzinfo=timezone.get_current_timezone()),
            completed_at=timezone.now(),
            notes=faker.sentence(),
            performed_by=None,
        )


def create_health(meters):
    for meter in meters:
        DeviceHealth.objects.create(
            meter=meter,
            last_seen=timezone.now(),
            status=random.choice(['online','offline','degraded']),
        )


def create_notifications(users_dict, count=50):
    """Create notifications for all users."""
    all_users = users_dict['superuser'] + users_dict['block_admin'] + users_dict['user']
    for _ in range(count):
        user = random.choice(all_users)
        Notification.objects.create(
            user=user,
            title=faker.sentence(nb_words=6),
            body=faker.paragraph(),
        )


class Command(BaseCommand):
    help = 'Populate water app with fake data'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing data before populating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing data...')
            Reading.objects.all().delete()
            ConsumptionSummary.objects.all().delete()
            Notification.objects.all().delete()
            DeviceHealth.objects.all().delete()
            Maintenance.objects.all().delete()
            Payment.objects.all().delete()
            Bill.objects.all().delete()
            Alert.objects.all().delete()
            Sensor.objects.all().delete()
            Meter.objects.all().delete()
            Apartment.objects.all().delete()
            Site.objects.all().delete()
            User = get_user_model()
            User.objects.all().delete()
            self.stdout.write('  ✓ All data cleared')
        
        self.stdout.write('Creating users...')
        users_dict = create_users(num_superusers=1, num_block_admins=5, num_residents=20)
        self.stdout.write(f'  ✓ Created 1 superuser, 5 block admins, 20 residents')
        
        self.stdout.write('Creating sites (blocks)...')
        sites = create_sites(users_dict['block_admin'], n=5)
        self.stdout.write(f'  ✓ Created {len(sites)} sites linked to block admins')
        
        self.stdout.write('Creating apartments...')
        apartments = create_apartments(sites, per_site=4)
        self.stdout.write(f'  ✓ Created {len(apartments)} apartments')
        
        self.stdout.write('Creating meters...')
        meters = create_meters(sites, apartments, per_site=1)
        self.stdout.write(f'  ✓ Created {len(meters)} meters (one per site)')
        
        self.stdout.write('Creating sensors...')
        sensors = create_sensors(meters, per_meter=2)
        self.stdout.write(f'  ✓ Created {len(sensors)} sensors')
        
        self.stdout.write('Creating readings... (this may take a while)')
        create_readings(sensors, count=500)
        self.stdout.write(f'  ✓ Created readings for all sensors')
        
        self.stdout.write('Creating alerts...')
        create_alerts(sites, count=30)
        self.stdout.write(f'  ✓ Created 30 alerts')
        
        self.stdout.write('Creating consumption summaries...')
        create_summaries(meters)
        self.stdout.write(f'  ✓ Created consumption summaries')
        
        self.stdout.write('Creating bills...')
        bills = create_bills(users_dict, sites, apartments, count=30)
        self.stdout.write(f'  ✓ Created {len(bills)} bills')
        
        self.stdout.write('Creating payments...')
        create_payments(bills)
        self.stdout.write(f'  ✓ Created payments for paid bills')
        
        self.stdout.write('Creating maintenance events...')
        create_maintenance(meters, count=30)
        self.stdout.write(f'  ✓ Created 30 maintenance events')
        
        self.stdout.write('Creating device health records...')
        create_health(meters)
        self.stdout.write(f'  ✓ Created health records for all meters')
        
        self.stdout.write('Creating notifications...')
        create_notifications(users_dict, count=50)
        self.stdout.write(f'  ✓ Created 50 notifications')
        
        self.stdout.write(self.style.SUCCESS('✓ Water app fake data population complete!'))
