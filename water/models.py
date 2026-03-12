from django.conf import settings
from django.db import models


class Site(models.Model):
    """Represents a block/compound of houses or apartments.

    Historically named ``Site`` to match the original schema, this is the
    "block" in user requirements.  A site is owned/managed by a single
    ``block_admin`` user through the ``user`` field. Only that user (or
    superusers) may view the block's dashboard.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='sites',
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class Apartment(models.Model):
    """Individual apartment/house within a block (``Site``).

    The apartment records the number of occupants so that distribution of a
    common water bill may be apportioned fairly.
    """

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='apartments')
    number = models.CharField(max_length=50)
    occupants = models.PositiveIntegerField(default=0)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='residences',
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.site.code} Apt {self.number}"



class Meter(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('maintenance', 'Maintenance'),
    ]

    site = models.ForeignKey(Site, on_delete=models.PROTECT, related_name='meters')
    apartment = models.ForeignKey(
        Apartment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meters',
    )
    serial_number = models.CharField(max_length=100, unique=True)
    model = models.CharField(max_length=100, blank=True)
    installed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.serial_number} @ {self.site.code}"


class ConsumptionSummary(models.Model):
    PERIOD_CHOICES = [
        ('day', 'Day'),
        ('month', 'Month'),
    ]

    period_date = models.DateField()
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    meter = models.ForeignKey(Meter, on_delete=models.CASCADE, related_name='summaries')
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='summaries')
    total_volume = models.DecimalField(max_digits=24, decimal_places=6, default=0)
    avg_flow = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    min_flow = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    max_flow = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('meter', 'period_type', 'period_date'),)

    def __str__(self):
        return f"Summary {self.meter.serial_number} {self.period_type} {self.period_date}"


class Bill(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bills')
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='bills')
    apartment = models.ForeignKey(
        Apartment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bills',
    )
    period_start = models.DateField()
    period_end = models.DateField()
    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    volume_consumed = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    currency = models.CharField(max_length=3, default='GHS')
    status = models.CharField(max_length=20, default='pending')
    issued_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Bill {self.id} - {self.site.code} - {self.amount_due}"


class BillOccupancy(models.Model):
    """Record of how many occupants were used when distributing a particular bill.

    This allows the number to vary for each billing period while still
    preserving the historical data.  When a bill is created the
    corresponding apartments' ``occupants`` fields are updated for convenience.
    """

    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='occupancies')
    apartment = models.ForeignKey(
        Apartment,
        on_delete=models.CASCADE,
        related_name='bill_occupancies',
    )
    occupants = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = (('bill', 'apartment'),)

    def __str__(self):
        return f"{self.occupants} residents for {self.apartment} on bill {self.bill_id}"


class Payment(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_at = models.DateTimeField()
    method = models.CharField(max_length=50, blank=True)
    reference = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Payment {self.amount} for bill {self.bill_id}"
