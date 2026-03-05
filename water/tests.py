from django.test import TestCase, Client
from django.utils import timezone

from accounts.models import User
from .models import (
    Site, Apartment, Meter, Sensor, Reading, ConsumptionSummary,
    Bill, Payment
)
from .models import BillOccupancy


class WaterDashboardTests(TestCase):
    def setUp(self):
        # create some data to exercise the view
        self.client = Client()
        # create three users with different roles
        self.block_admin = User.objects.create_user(
            email="admin@example.com",
            password="pass",
            role='block_admin'
        )
        self.superuser = User.objects.create_user(
            email="super@example.com",
            password="pass",
            role='superuser'
        )
        self.regular_user = User.objects.create_user(
            email="user@example.com",
            password="pass",
            role='user'
        )
        self.site = Site.objects.create(
            name="Test Site",
            code="TS-1",
            user=self.block_admin
        )
        self.meter = Meter.objects.create(site=self.site, serial_number="MTR-100")
        self.sensor = Sensor.objects.create(meter=self.meter, sensor_type=Sensor.SensorType.FLOW)

        today = timezone.now().date()
        ConsumptionSummary.objects.create(
            period_date=today,
            period_type='day',
            meter=self.meter,
            site=self.site,
            total_volume=123.45,
        )

        # user and bills/payments (use block_admin)
        self.bill = Bill.objects.create(
            user=self.block_admin,
            site=self.site,
            period_start=today,
            period_end=today,
            amount_due=200,
            status='pending',
        )
        # partial payment to test percentage calculation
        Payment.objects.create(bill=self.bill, amount=50, paid_at=timezone.now())

        # create a recent reading
        Reading.objects.create(
            sensor=self.sensor,
            meter=self.meter,
            timestamp=timezone.now(),
            value=10.0,
        )

    def test_dashboard_context(self):
        response = self.client.get('/')  # water app is root in urlpatterns
        self.assertEqual(response.status_code, 200)
        stats = response.context['stats']
        self.assertAlmostEqual(stats['total_consumption_m3'], 123.45)
        self.assertEqual(stats['active_meters'], 1)
        self.assertEqual(stats['outstanding_bills'], 1)
        # collection rate should be (50/200)*100 == 25
        self.assertEqual(stats['collection_rate'], 25)

        readings = response.context['latest_readings']
        self.assertTrue(len(readings) >= 1)
        first = readings[0]
        self.assertEqual(first['meter_id'], 'MTR-100')
        self.assertEqual(first['consumption'], 10.0)

    def test_block_and_apartment_dashboards(self):
        # login as block admin
        self.client.force_login(self.block_admin)

        # create a second apartment with its own meter/reading
        block = self.site  # our site acts as block
        apt1 = Apartment.objects.create(site=block, number="1A", occupants=3)
        apt2 = Apartment.objects.create(site=block, number="1B", occupants=2)
        # reassign existing meter to apt1
        self.meter.apartment = apt1
        self.meter.save()
        # add a second meter and reading for apt2
        meter2 = Meter.objects.create(site=block, apartment=apt2, serial_number="MTR-101")
        Reading.objects.create(sensor=self.sensor, meter=meter2, timestamp=timezone.now(), value=5)

        # bills attached to apartments
        bill1 = Bill.objects.create(user=self.block_admin, site=block, apartment=apt1,
                                    period_start=timezone.now().date(), period_end=timezone.now().date(),
                                    amount_due=100, status='pending')
        bill2 = Bill.objects.create(user=self.block_admin, site=block, apartment=apt2,
                                    period_start=timezone.now().date(), period_end=timezone.now().date(),
                                    amount_due=200, status='pending')

        Payment.objects.create(bill=bill1, amount=100, paid_at=timezone.now())

        # block dashboard should include both apartments
        resp_block = self.client.get(f'/block/{block.pk}/')
        self.assertEqual(resp_block.status_code, 200)
        stats_block = resp_block.context['stats']
        self.assertEqual(stats_block['active_meters'], 2)
        self.assertEqual(stats_block['outstanding_bills'], 1)  # one unpaid

        # apartment dashboards
        resp_apt1 = self.client.get(f'/apartment/{apt1.pk}/')
        self.assertEqual(resp_apt1.status_code, 200)
        stats_apt1 = resp_apt1.context['stats']
        self.assertEqual(stats_apt1['active_meters'], 1)
        self.assertEqual(stats_apt1['outstanding_bills'], 0)  # paid

        resp_apt2 = self.client.get(f'/apartment/{apt2.pk}/')
        stats_apt2 = resp_apt2.context['stats']
        self.assertEqual(stats_apt2['active_meters'], 1)
        self.assertEqual(stats_apt2['outstanding_bills'], 1)

    def test_role_based_access_control(self):
        """Test that roles control dashboard access."""
        site = self.site  # owned by block_admin
        apt = Apartment.objects.create(site=site, number="1A", occupants=2)

        # Block admin can access their site and apartments
        self.client.force_login(self.block_admin)
        resp = self.client.get(f'/block/{site.pk}/')
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f'/apartment/{apt.pk}/')
        self.assertEqual(resp.status_code, 200)

        # Superuser can access any site/apartment
        self.client.force_login(self.superuser)
        resp = self.client.get(f'/block/{site.pk}/')
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(f'/apartment/{apt.pk}/')
        self.assertEqual(resp.status_code, 200)

        # Regular user cannot access block/apartment dashboards
        self.client.force_login(self.regular_user)
        resp = self.client.get(f'/block/{site.pk}/')
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(f'/apartment/{apt.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_role_routing_from_home(self):
        """Clicking the water link (root) should deliver the correct dashboard."""
        # superuser
        self.client.force_login(self.superuser)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'superuser_dashboard.html')

        # block admin
        self.client.force_login(self.block_admin)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'block_admin_dashboard.html')

        # regular user
        self.client.force_login(self.regular_user)
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'user_dashboard.html')

        # Block admin from another block cannot access
        other_admin = User.objects.create_user(
            email="other_admin@example.com",
            password="pass",
            role='block_admin'
        )
        other_site = Site.objects.create(
            name="Other Site",
            code="OS-1",
            user=other_admin
        )
        apt = Apartment.objects.create(site=self.site, number="2A", occupants=2)
        self.client.force_login(other_admin)
        resp = self.client.get(f'/block/{self.site.pk}/')
        self.assertEqual(resp.status_code, 404)
        resp = self.client.get(f'/apartment/{apt.pk}/')
        self.assertEqual(resp.status_code, 404)

    def test_enter_bill_with_occupancy(self):
        """Block admin can supply per‑period occupant counts when creating a bill."""
        self.client.force_login(self.block_admin)
        block = self.site
        # create a couple of apartments with initial occupancy
        apt1 = Apartment.objects.create(site=block, number="A1", occupants=2)
        apt2 = Apartment.objects.create(site=block, number="A2", occupants=1)

        # GET page should display inputs populated with current values
        resp_get = self.client.get(f'/block/{block.pk}/enter-bill/')
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, f'name="occupants_{apt1.id}"')
        self.assertContains(resp_get, f'value="2"')
        self.assertContains(resp_get, f'name="occupants_{apt2.id}"')
        self.assertContains(resp_get, f'value="1"')

        # POST a bill with overridden occupants: apt1 -> 3, apt2 -> 1
        today = timezone.now().date()
        resp = self.client.post(
            f'/block/{block.pk}/enter-bill/',
            data={
                'period_start': today,
                'period_end': today,
                'total_amount': '400',
                f'occupants_{apt1.id}': '3',
                f'occupants_{apt2.id}': '1',
            }
        )
        # should redirect back to dashboard
        self.assertEqual(resp.status_code, 302)
        # two bills created with correct shares (3/4*400=300, 1/4*400=100)
        bills = Bill.objects.filter(site=block).order_by('apartment__number')
        # there may be pre-existing bills; filter by period to be certain
        bills = bills.filter(period_start=today, period_end=today)
        self.assertEqual(bills.count(), 2)
        amounts = sorted([float(b.amount_due) for b in bills], reverse=True)
        self.assertEqual(amounts, [300.0, 100.0])
        # apartments updated
        apt1.refresh_from_db()
        apt2.refresh_from_db()
        self.assertEqual(apt1.occupants, 3)
        self.assertEqual(apt2.occupants, 1)
        # occupancy records exist
        occs = BillOccupancy.objects.filter(bill__in=bills).order_by('apartment__number')
        self.assertEqual(len(occs), 2)
        occ_values = sorted([o.occupants for o in occs], reverse=True)
        self.assertEqual(occ_values, [3, 1])

    def test_enter_bill_with_no_occupants_error(self):
        """Submitting zero occupants should produce an error message."""
        self.client.force_login(self.block_admin)
        block = self.site
        apt = Apartment.objects.create(site=block, number="Z1", occupants=0)
        today = timezone.now().date()
        resp = self.client.post(
            f'/block/{block.pk}/enter-bill/',
            data={
                'period_start': today,
                'period_end': today,
                'total_amount': '100',
                f'occupants_{apt.id}': '0',
            }
        )
        # page should re-render with error
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No occupants recorded for any apartments')
