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

Optionally create an administrator account:

```bash
python manage.py createsuperuser
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
