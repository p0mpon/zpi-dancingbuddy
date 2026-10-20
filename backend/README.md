# Dancing Buddy — backend

Django 6.1 + Django REST Framework + PostgreSQL, run with Docker Compose.

## First run

1. Copy the env template and fill in secrets (`DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`):
   ```
   cp backend/.env.example backend/.env
   ```
   Generate a secret key with `python -c "import secrets; print(secrets.token_urlsafe(50))"`.
2. From the repo root:
   ```
   docker compose up --build
   ```
   This starts Postgres (`db`), waits until it's healthy, runs migrations and serves Django on http://localhost:8000.
3. Create an admin user:
   ```
   docker compose exec dancing-buddy-backend python manage.py createsuperuser
   ```
   Then log in at http://localhost:8000/admin/.

## Settings

`zpi_app/settings/` is a package:

| Module    | Used by                         | Notes                                   |
|-----------|---------------------------------|-----------------------------------------|
| `base.py` | everything (imported by others) | shared config, reads env vars           |
| `dev.py`  | `manage.py`, `wsgi.py` default  | `DEBUG=True`, insecure key fallback     |
| `prod.py` | `asgi.py` default               | requires all secrets, HTTPS hardening   |

Production is served over **ASGI** with uvicorn (`uvicorn zpi_app.asgi:application`).
`wsgi.py` only exists because `runserver` (dev) uses it.
| `test.py` | `manage.py test --settings=…`   | fast hashing, separate media folder     |

`DJANGO_SETTINGS_MODULE` in `.env` overrides the defaults. Audit production settings with:
```
docker compose exec dancing-buddy-backend python manage.py check --deploy --settings=zpi_app.settings.prod
```

## Common commands

```
docker compose exec dancing-buddy-backend python manage.py makemigrations
docker compose exec dancing-buddy-backend python manage.py test --settings=zpi_app.settings.test
docker compose down        # stop (DB data kept in the postgres_data volume)
docker compose down -v     # stop AND wipe the database
```

## Running without Docker

Possible (Python 3.14, `python -m venv .venv`, `pip install -r requirements.txt`), but you need a
Postgres server and the variables from `.env` exported in your shell; Django doesn't read `.env` itself.
Set `POSTGRES_HOST=localhost` and start only the DB with `docker compose up db`.

## How to run (if you're on Wi*dows)

```powershell
docker run --rm -it -p 8000:8000 `
  -v "${PWD}\zpi_app:/app/zpi_app" `
  -v "${PWD}\audio_analysis:/app/audio_analysis" `
  dancingbuddy-backend
```
This will mount the local source folders as volumes and you will be able to reload the application without having to rebuild the image.

Otherwise you can simply follow the instructions below:

### Essentia usage guide:

insert music into essentia/insert_example_music

load the track using ```MusicLoader.load_track()```

analyse the track using MusicProcessor, available methods:
* ```song_segmentation()```
* ```beat_detection()```
* ```onset_detection()```