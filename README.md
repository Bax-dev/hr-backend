# Workiva Backend

The Workiva backend is a Django application backed by PostgreSQL and Redis.

## Prerequisites

Install the following before setting up the project:

- Python 3.10 or newer
- PostgreSQL
- Redis
- `pip`

## Install dependencies

From the repository root, enter the backend directory:

```bash
cd workiva-backend
```

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.venv\Scripts\Activate.ps1
```

Upgrade `pip` and install the Python dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Configure the application

Copy the example environment file:

```bash
cp .env.example .env
```

On Windows PowerShell, use:

```powershell
Copy-Item .env.example .env
```

Update `.env` with your local PostgreSQL credentials. The default configuration expects:

```text
database: hr_app_db
user: postgres
password: postgres
host: 127.0.0.1
port: 5432
```

Create the database if it does not already exist:

```bash
createdb -U postgres hr_app_db
```

Make sure Redis is running at `redis://127.0.0.1:6379/1`, or change `REDIS_URL` in `.env`.

## Initialize and run

Apply the database migrations:

```bash
python manage.py migrate
```

Optionally create an administrator account interactively:

```bash
python manage.py createsuperuser
```

Or bootstrap one non-interactively from `SUPERADMIN_EMAIL` / `SUPERADMIN_PASSWORD` in
`.env` — safe to run repeatedly (a no-op once the account exists, unless
`--reset-password` is passed):

```bash
python manage.py create_superadmin
```

Start the development server:

```bash
python manage.py runserver
```

The API will be available at <http://127.0.0.1:8000/>.

## Verify the installation

Run Django's checks and test suite:

```bash
python manage.py check
python manage.py test
```

When you finish working, deactivate the virtual environment with:

```bash
deactivate
```
# Bulk employee notification emails

Company administrators can create an in-app notification and queue an email for every active employee:

```http
POST /api/v1/notifications/bulk/
Authorization: Bearer <token>
Content-Type: application/json

{"title":"Office closure","body":"The office will be closed on Friday."}
```

Pass `employeeIds` as an optional array to target selected active employees. The endpoint returns `202 Accepted` with a campaign ID. Delivery progress is available from `GET /api/v1/notifications/bulk/<campaign-id>/`.

Run the durable queue worker as a separate process:

```bash
python manage.py process_notification_emails
```

Use `--batch-size 100` to tune each claim or `--once` for a scheduler/cron deployment. Failed deliveries are retried three times with exponential backoff; each recipient gets an individual email to prevent address disclosure.
