# Generated manually to add BillOccupancy model

from django.db import migrations, models
import django.db.models.deletion


def create_billoccupancy(apps, schema_editor):
    # the model is defined later in this file via CreateModel operation
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('water', '0002_site_user_apartment_bill_apartment_meter_apartment'),
    ]

    operations = [
        migrations.CreateModel(
            name='BillOccupancy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('occupants', models.PositiveIntegerField(default=0)),
                ('apartment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bill_occupancies', to='water.apartment')),
                ('bill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='occupancies', to='water.bill')),
            ],
            options={
                'unique_together': {('bill', 'apartment')},
            },
        ),
    ]
