from django.db import models
from django.conf import settings


class Dustbin(models.Model):
    """Represents a dustbin in a site."""

    site = models.ForeignKey('water.Site', on_delete=models.CASCADE, related_name='dustbins')
    serial_number = models.CharField(max_length=100, unique=True)
    model = models.CharField(max_length=100, blank=True)
    installed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='active')
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.serial_number} @ {self.site.code}"


class DustbinBill(models.Model):
    """Represents a single dustbin bill for an apartment."""

    bill = models.ForeignKey('water.Bill', on_delete=models.CASCADE, related_name='dustbin_bills')
    apartment = models.ForeignKey('water.Apartment', on_delete=models.CASCADE, related_name='dustbin_bills')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()

    def __str__(self):
        return f"Dustbin bill for {self.apartment} for bill {self.bill.id}"
