# voltaqua

Django project for water distribution to households within a block of houses.

## Static files and image handling

This project uses [Whitenoise](http://whitenoise.evans.io/en/stable/) to serve static assets (CSS, JS and images) directly from Django without needing a separate web server. Configuration has been added to `core/settings.py`:

* `WhiteNoiseMiddleware` is enabled in the middleware stack.
* `STATIC_ROOT` is set to `BASE_DIR / 'staticfiles'` and `STATICFILES_STORAGE` uses `CompressedManifestStaticFilesStorage` for compression and caching.

After changing or adding static assets run:

```bash
python manage.py collectstatic
```

The `pillow` library is installed to allow image processing (thumbnails, generation, etc.). You can use it in views or management commands to create/resize PNGs or JPGs; Django will then serve them through the usual static file mechanisms (or via media if you set up `MEDIA_ROOT`).

Place your images under `base/static/img/` (or the appropriate app’s `static/` folder) and refer to them with the `{% static %}` template tag.

### Profile Images
A `profile_image` field was added to the custom `User` model. After pulling these changes run:

```bash
python manage.py makemigrations accounts
python manage.py migrate
```

This will create the media directory structure and allow users to upload avatars. Use the `/accounts/profile/` page to edit your profile picture.


Quick start

1. Create a virtualenv and install dependencies:

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

2. Run migrations and start server:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

3. API endpoints are under `/api/` (Blocks, Households, Meters, ConsumptionRecords).

The water app now supports separate dashboards for **blocks** (treated as `Site` objects) and individual **apartments**. Three user roles with distinct permissions manage the system:

**User Roles:**

1. **Superuser** (`role='superuser'`) – Can view all blocks and apartments, manage global settings.
2. **Block Admin** (`role='block_admin'`) – Assigned to a specific block (`Site.user`); can only view dashboards for their assigned block and its apartments.
3. **User** (`role='user'`) – Regular resident/occupant; cannot view block or apartment dashboards (may view global overview in future).

Each block may be assigned to a single block admin user via the ``user`` field on `Site`; this user will automatically have permission to view that block's dashboard and the dashboards of any apartments within it. Only superusers can view blocks/apartments they do not own. Administrators can register apartments under a block; meters, readings and bills may be associated with specific apartments to enable fair distribution of the compound bill.

Use the following URLs to access the water management system:

* `/` – **Home Dashboard** (role-based routing): when logged in, clicking the Water button or visiting the root URL will forward the user to the dashboard appropriate to their role.
  - **Superuser** sees global overview with all blocks, apartments, and system metrics.
  - **Block Admin** sees their assigned block with apartment breakdown.
  - **User** sees a welcome page with information about their account.
* `/block/<site_id>/` – view detailed statistics for a particular block (with permission checks).
* `/apartment/<apartment_id>/` – view consumption and billing data for a specific apartment (with permission checks).

Add apartments via the Django admin or by creating `Apartment` instances in code, and link meters to them using the new `apartment` foreign key on `Meter`.

**Creating Users with Roles:**

When creating users, assign the appropriate role:

```python
from accounts.models import User

# Create a superuser
superuser = User.objects.create_user(
    email='admin@example.com',
    password='secure_password',
    role='superuser'
)

# Create a block admin
block_admin = User.objects.create_user(
    email='block_manager@example.com',
    password='secure_password',
    role='block_admin'
)

# Create a regular user
resident = User.objects.create_user(
    email='resident@example.com',
    password='secure_password',
    role='user'
)
```

Then assign the block admin to a site:

```python
from water.models import Site

block = Site.objects.create(
    name='Downtown Block A',
    code='DBA-1',
    user=block_admin  # assign the block admin
)
```

If you want, I can run migrations and add example fixtures next.
# voltaqua
An app for the distribution of water and electricity bills. The app has two phases. one phase for water bill distribution and the other phase for electricity bill distribution.

WATER BILL DISTRIBUTION:
This section of the app is designed to be used to distribute water among tenant of a compount house or apartment within a block of apartments. The app has a administrator who enters the monthly water bill given to the compound house of apartments by the GWCL. He also registers the apartments onto the dashboard. He is also responsible for entering the number of people in each apartment on monthly basis just like the monlthly bill. The app should also allow the appartment heads to have an interface that will enalb them to view the bill for the entire block and also thier individual apartments only. the admin should also be able to enter payments recieved from each of the appartments and this shold also be seen by the individual apartment. 