# Cleanups

Small known issues, left for later.

## Orphaned file when the upload INSERT fails

**Where:** `videos/services.py`, `upload_video()`

**Problem:** `Video.objects.create()` first writes the file (in `FileField.pre_save()`), then runs
the INSERT. If the INSERT fails (DB down, constraint error, ...), the file stays in
`media/videos/user_<id>/` with no row pointing to it.

**Fix:** keep `FileField` (and `upload_to=video_upload_path`), but save in a `try` and delete
the file if it was already written:

```python
def upload_video(*, owner, title, file, description=''):
    video = Video(owner=owner, title=title, description=description,
                  path_to_resource=file, file_size=float(file.size))
    try:
        video.save()                            # writes the file, then INSERTs
    except Exception:
        if video.path_to_resource._committed:   # the file was already written
            video.path_to_resource.storage.delete(video.path_to_resource.name)
        raise
    return video
```

Don't save the file by hand with `default_storage.save()` and pass a path string instead: that
would put the path rule in two places (`video_upload_path` and the service).

**Test:** make only the INSERT fail, after the file is written: patch `Video._do_insert`
with `side_effect=IntegrityError` (don't patch `save()` / `save_base()`, those run *before*
`pre_save()`, so no file would be written and the test would prove nothing). Call
`services.upload_video()`, expect `IntegrityError`, and check that `MEDIA_ROOT/videos/` is empty.

**Done when:** the test above passes and the "Known limitation" comment in `upload_video`
is removed.

## Celery worker concurrency is hard-coded to 1

**Where:** `docker-compose.yml` (`celery-worker` service, `--concurrency=1`),
`zpi_app/settings/base.py` (Celery section)

**Problem:** the number of parallel analyses per worker container is fixed in the compose
command. Changing it means editing a file in git, and dev and prod can't use different values.
The right number isn't known yet either: it depends on how much CPU and RAM one real analysis
uses, and the analysis isn't connected yet (`run_analysis` in `videos/tasks.py` is a TODO).

**Fix:** read it from the environment in settings, like `POSTGRES_POOL_MAX_SIZE`:

```python
# zpi_app/settings/base.py
# Parallel analyses per worker container. Each one is a separate process.
CELERY_WORKER_CONCURRENCY = int(env("CELERY_WORKER_CONCURRENCY", "1"))
```

- Remove `--concurrency=1` from the compose `command`: a command-line flag overrides the setting.
- Add `CELERY_WORKER_CONCURRENCY=1` to `.env.example`.
- Don't use `${CELERY_CONCURRENCY:-1}` in `docker-compose.yml`: compose substitutes variables from
  the shell or a `.env` next to `docker-compose.yml`, not from `backend/.env`, so it would
  silently stay at the default.

**Choosing the value** (once the real analysis is connected): run one analysis and check its peak
RAM with `docker stats`. Then concurrency ≈ min(CPU cores, free RAM ÷ RAM per analysis), leaving
room for the web server and Postgres. Each process also has its own DB pool
(`POSTGRES_POOL_MAX_SIZE`), so containers × concurrency × pool size must stay under Postgres's
`max_connections` (100 by default). For more throughput, add containers
(`docker compose up -d --scale celery-worker=N`) instead of raising concurrency past the core count.

**Test:** `docker compose logs celery-worker` shows `concurrency: N (prefork)` after setting
`CELERY_WORKER_CONCURRENCY=N` in `backend/.env` and running `docker compose up -d celery-worker`.

**Done when:** the value comes from `.env`, `--concurrency` is gone from `docker-compose.yml`,
and the production value is picked from a measurement, not a guess.
