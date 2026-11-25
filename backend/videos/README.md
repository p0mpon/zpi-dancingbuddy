# Videos API

Upload dance videos, stream them back to the player, and get their pose analysis.
Django REST Framework, PostgreSQL, Celery + Redis for the analysis.

- [Endpoints](#endpoints)
- [Architecture](#architecture)
- [Data flow](#data-flow)

---

## Endpoints

Routes are registered in `zpi_app/urls.py` (`router.register('videos', VideoViewSet)`).
`{id}` is a number (`lookup_value_regex = r'\d+'`).

### Authentication

Login is the default for every endpoint (`IsAuthenticated` in `settings/base.py`). Three GETs opt out with
`AllowAny`, so a visitor can look around the library without an account (`docs/api-decisions.md` D7.6):

| Open without login | A visitor gets |
|---|---|
| `GET /api/library/` | public videos only; `?scope=mine` → 401 |
| `GET /api/library/{id}/` | a public video; a private one → 404 |
| `GET /api/videos/{id}/stream/` | a public video's file; a private one → 404 |

For a visitor `is_mine` and `liked_by_me` are `false` and `best_score` is `null`.

| How | Where | Notes |
|---|---|---|
| Session cookie | all environments | Log in at `/admin/` or `/api-auth/login/`. Works for `<video src=...>`. Writes (POST/PATCH/DELETE) need the CSRF token. |
| Basic Auth | **dev only** (`settings/dev.py`) | For Postman / curl: `curl -u user:pass ...`. No CSRF needed. |

Not logged in → **401** on every other endpoint.

**Who sees what** (one rule, `VideoQuerySet` in `models.py`):

| Method | Videos | Used by |
|---|---|---|
| `Video.objects.owned_by(user)` | the user's own uploads | everything under `/api/videos/` except stream / analysis; library `scope=mine` |
| `Video.objects.public()` | `visibility = public` and the owner is active | liking a video |
| `Video.objects.visible_to(user)` | `public()` **or** the user's own; just `public()` for a visitor | the library, stream, analysis, removing a like |

A video outside that set gives **404** (not 403), so the API doesn't reveal that the id exists.

### Summary

`/api/videos/` = **my uploads** (`VideoViewSet`):

| Method | URL | What | Who | Success | Errors |
|---|---|---|---|---|---|
| `GET` | `/api/videos/` | list my videos, filtered + paginated | owner | 200 | 400, 401 |
| `POST` | `/api/videos/` | upload a video, queues the analysis | | 201 | 400, 401 |
| `GET` | `/api/videos/{id}/` | one video | owner | 200 | 401, 404 |
| `PATCH` | `/api/videos/{id}/` | edit title, description, song fields, difficulty, visibility | owner | 200 | 400, 401, 404, 409 |
| `DELETE` | `/api/videos/{id}/` | delete the row and the file | owner | 204 | 401, 404 |
| `GET` | `/api/videos/{id}/stream/` | the video file, with Range support | owner or public; no login needed for public | 200, 206 | 404, 416 |
| `GET` | `/api/videos/{id}/analysis/` | the whole analysis JSON | owner or public | 200 | 401, 404, 409 |
| `POST` | `/api/videos/{id}/reanalyze/` | run a failed analysis again (needs runs left, max 5) | owner | 202 | 401, 404, 409 |

`/api/library/` = **what I can dance**: public videos + all my own (`LibraryViewSet`, DAN-141):

| Method | URL | What | Success | Errors |
|---|---|---|---|---|
| `GET` | `/api/library/` | browse; `?scope=all` (default) or `mine`; filtered + paginated; no login needed | 200 | 400, 401 (`scope=mine` without login) |
| `GET` | `/api/library/liked/` | the videos I liked, newest like first; filtered + paginated | 200 | 400, 401 |
| `GET` | `/api/library/{id}/` | one video (public, or mine); no login needed for public | 200 | 404 |
| `PUT` | `/api/library/{id}/like/` | like a public video (idempotent) | 200 | 401, 404 |
| `DELETE` | `/api/library/{id}/like/` | remove my like (idempotent) | 200 | 401, 404 |

There is no `/api/library/{id}/stream/`: the library page plays `/api/videos/{id}/stream/`.

### Filters, ordering, pages

Shared by `/api/videos/`, `/api/library/` and `/api/library/liked/` (`filters.py`):

| Param | Meaning |
|---|---|
| `search` | case-insensitive partial match on title, song title, song author, author nickname |
| `difficulty` | `beginner`, `intermediate` or `advanced` |
| `author` | the whole nickname, ignoring case; unknown nickname → empty page |
| `ordering` | `newest` (default; publish date, or creation date for a private video), `likes`, `played` |
| `limit`, `offset` | page size (default 20, max 100) and how many to skip |
| `scope` | library only: `all` (default) or `mine` |
| `analysis_status`, `visibility` | `/api/videos/` only |

A wrong value (`?difficulty=foo`) → **400** `{"difficulty": ["\"foo\" is not a valid choice."]}`.
A missing or empty param = no filter. Every list answers
`{"count": 42, "next": "<url or null>", "previous": "<url or null>", "results": [...]}`.

### The library video object

Returned by the three library GETs (`LibraryVideoSerializer`, `PublicVideo` in `docs/openapi.yaml`):
`id, title, description, song_title, song_author, difficulty, duration_seconds, thumbnail_url, visibility,
published_at, author_nickname, author_avatar_url, is_mine, likes_count, liked_by_me, times_played,
best_score, created_at`.

| Field | Notes |
|---|---|
| `author_nickname` | the public name; the private `username` is never in any response |
| `is_mine`, `visibility` | for the "private" badge on my own videos |
| `likes_count` | the stored `Video.likes_count` column (kept in sync by `likes/services.py`) |
| `liked_by_me`, `times_played`, `best_score` | computed for the logged-in user in the list query (`annotate_for_library`) |

`PUT` / `DELETE .../like/` answer `{"likes_count": 3, "liked_by_me": true}`.

`PUT` (full replace) is not supported → 405. `POST /analysis/` → 405: the analysis only
starts on upload, on an automatic retry, or on `POST /reanalyze/`.

### The video object

Returned by list, retrieve, upload and PATCH (`VideoSerializer`):

```json
{
  "id": 42,
  "title": "Salsa basic step",
  "description": "Slow version",
  "file_size": 48213504.0,
  "analysis_status": "pending",
  "analysis_error_code": null,
  "thumbnail_url": null,
  "created_at": "2026-11-03T12:00:00Z"
}
```

| Field | Notes |
|---|---|
| `file_size` | bytes; read-only, computed on upload |
| `analysis_status` | read-only: `pending` → `processing` → `done` or `failed` (see [Analysis status](#analysis-status)) |
| `analysis_error_code` | read-only: null, or 1 / 2 / 3 / 4 / 5 / 99 when `failed` |
| `thumbnail_url` | read-only: WebP, longest side 720 px; null until generated |

Not in the object: `owner` (always you), the file path (use `/stream/`), `json_analysis` (use `/analysis/`, it can be large).

### `GET /api/videos/`

Your videos, newest first, as a page (see [Filters, ordering, pages](#filters-ordering-pages)).
No videos = `{"count": 0, "next": null, "previous": null, "results": []}` with 200, not 404.

### `POST /api/videos/`

`multipart/form-data`:

| Field | Required | Rules |
|---|---|---|
| `title` | yes | max 200 characters |
| `description` | no | max 500 characters, default `""` |
| `file` | yes | extension `mp4`, `mov` or `webm`; max 500 MB |

→ **201** with the video object (`analysis_status: "pending"`). The file is stored as
`media/videos/raw/<random>.<ext>` and the analysis is queued; the normalized copy replaces it as `media/videos/normalized/<same name>_normalized.mp4`. No path contains a user id.
An `owner` field in the form is ignored. → **400** with the field errors, e.g.
`{"file": ["Allowed file types: mp4, mov, webm."]}`.

### `GET /api/videos/{id}/`

→ **200** with the video object. The frontend checks `analysis_status` here before asking for `/analysis/`.

### `PATCH /api/videos/{id}/`

JSON or `multipart/form-data`; send only what changes:

| Field | Effect |
|---|---|
| `title`, `description` | renamed; the analysis is kept |
| `file` (multipart) | same rules as upload. Replaces the file, clears `json_analysis`, sets `analysis_status` back to `pending` and queues a new analysis. The old file is deleted. |

`file_size` and `analysis_status` in the body are ignored. `{}` changes nothing. → **200** with the updated object.

### `DELETE /api/videos/{id}/`

→ **204**, no body. The row is deleted, then the file (once the delete is committed).

### `GET /api/videos/{id}/stream/`

The video file for `<video src="/api/videos/42/stream/">`. The player seeks by sending
`Range` headers (bytes, not seconds; it works out the offsets from the file's index):

| Request | Response |
|---|---|
| no `Range` | **200**, whole file, `Accept-Ranges: bytes` |
| `Range: bytes=0-99` / `bytes=100-` / `bytes=-100` | **206**, only those bytes, `Content-Range: bytes START-END/SIZE` |
| malformed or several ranges | ignored → **200** with the whole file |
| range starts past the end | **416**, `Content-Range: bytes */SIZE` |

`?download=1` → `Content-Disposition: attachment; filename="<title>.<ext>"` (saved instead of played).

```bash
curl -u user:pass -H "Range: bytes=0-99" -i http://localhost:8000/api/videos/42/stream/
```

### `GET /api/videos/{id}/analysis/`

→ **200** with `json_analysis` exactly as stored, once `analysis_status` is `done`.
→ **409** `{"detail": "Video is not analysed yet."}` while it's `pending`, `processing` or `failed`.

The JSON format isn't decided yet (list of `Frame` dicts vs DAN-35's `ChoreoData`).

### Analysis status

```mermaid
stateDiagram-v2
    [*] --> pending: POST upload
    pending --> processing: a run starts (analysis_runs + 1)
    processing --> done: normalized, thumbnail, run_analysis() returned
    processing --> processing: normalization timeout or unexpected error, tries left: retried after 10 / 30 / 60 / 120 s (each try is a run)
    processing --> failed: any other error, or the tries are used up: analysis_error_code set
    failed --> pending: POST reanalyze (needs analysis_runs < 5)
```

A run is capped at `MAX_ANALYSIS_RUNS = 5` (automatic retries and reanalyze share the counter). The error codes
(`analysis_error_code`, `docs/api-decisions.md` D3.8) are 1 file missing, 2 unreadable, 3 normalization failed,
4 normalization timeout (retried), 5 analysis failed, 99 unknown (retried). `analysis_runs` and `is_normalized` are
not in the API.

---

## Architecture

### Layers

Each layer has one job. The rule that matters most: **every write goes through `services.py`**.

| Layer | File | Does | Never does |
|---|---|---|---|
| View | `views.py` | HTTP only: find the video (through `VideoQuerySet`: `owned_by` / `visible_to`, 404 otherwise), validate with a serializer, call a service, return the response + status code | validate field values itself, write to the DB |
| Serializer | `serializers.py` | whitelist fields, convert types, validate the request; object → JSON | read from the DB, save (no `serializer.save()`) |
| Service | `services.py` | every write and side effect: DB rows, files, queueing the analysis. Plain functions, keyword-only args | know about `request` / HTTP |
| Task | `tasks.py` | background work in the Celery worker; writes through services, like views do | run inside a web request |
| Model | `models.py` | data, DB constraints, small `@property` facts (`is_analysed`, ...) | know about HTTP or Celery |

### Modules

| File | What's in it                                                                                                                                                                                                                                          |
|---|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `models.py` | `Video` (the VIDEO table from `db/diagram/v2.md`), `VideoQuerySet` (who sees which video: `owned_by`, `public`, `visible_to`), `AnalysisStatus` and `AnalysisError` choices, `MAX_ANALYSIS_RUNS`, retry constants, `video_upload_path()` (where files are stored), constraints: `file_size >= 0`, status is one of the four values, error code valid and only on a failed row                                                          |
| `serializers.py` | `VideoSerializer` (output + PATCH; a `ModelSerializer`, plus a write-only `file`), `VideoUploadSerializer` (POST; a plain `Serializer`, because the request's `file` isn't a model field), file checks `validate_filename()` / `validate_file_size()` |
| `views.py` | `VideoViewSet` (`/api/videos/`): one method per endpoint (`list`, `create`, `retrieve`, `partial_update`, `destroy`, and the `stream`, `analysis`, `reanalyze` actions). `LibraryViewSet` (`/api/library/`): `list`, `retrieve`, and the `liked`, `like` actions; likes are written by `likes/services.py` |
| `filters.py` | the query params of the video lists: `VideoFilterParams` / `LibraryFilterParams` / `MyVideosFilterParams` (validation), `filter_videos()` (filters + ordering), `annotate_for_library()` / `annotate_times_played()` / `only_liked_by()` (per-request values as subqueries) |
| `pagination.py` | `VideoPagination`: `?limit=&offset=`, max 100 per page |
| `services.py` | `upload_video`, `update_video`, `delete_video`, `start_analysis` (queues the task), `reanalyze_video`, and the writes of a run: `mark_video_processing`, `set_analysis_result`, `update_video_file`, `set_video_thumbnail`                                                                                                       |
| `tasks.py` | `normalize_video_file` (starts a run: normalize once, Celery retry, error codes), `analyse_video` (thumbnail + analysis), `run_analysis()` (the entry point of the real analysis) |
| `../core/ffmpeg.py` | ffprobe / ffmpeg wrappers shared with `dance_attempts`: `probe_video`, `read_duration_seconds`, `normalize_video`, `extract_frame`. No DB, no models (replaces `media_info.py`) |
| `streaming.py` | `range_file_response()` (200 / 206 / 416), `parse_range_header()` (pure, unit-tested), `read_chunks()` (64 KB at a time)                                                                                                                              |
| `admin.py` | `Video` in the Django admin (`/admin/`), analysis fields read-only |
| `tests.py` | `/api/videos/` API tests, task tests, Range parser tests |
| `tests_processing.py` | normalization, thumbnail, error codes, retries, reanalyze (real ffmpeg clips) |
| `tests_library.py` | DAN-141: `VideoQuerySet`, filters, annotations, `/api/library/` (list, detail, liked list, like) |

Outside the app:

| File | Role |
|---|---|
| `zpi_app/urls.py` | registers `VideoViewSet` under `/api/videos/` and `LibraryViewSet` under `/api/library/` on the router |
| `zpi_app/celery.py` | the Celery app; reads `CELERY_*` settings, finds `tasks.py` |
| `zpi_app/__init__.py` | loads the Celery app when Django starts |
| `zpi_app/settings/base.py` | REST framework defaults, media folder, `CELERY_BROKER_URL` |
| `zpi_app/settings/test.py` | `CELERY_TASK_ALWAYS_EAGER`: tests run tasks inline, no Redis needed |
| `docker-compose.yml` | `db` (Postgres), `redis`, `dancing-buddy-backend` (Django), `celery-worker` |

### Decisions worth knowing

- **Files are deleted only after the DB transaction commits** (`transaction.on_commit`), so a
  rolled-back delete never loses the file.
- **The analysis is queued after commit too**, so the worker never looks for a row that isn't saved yet.
  If Redis is down, the upload still succeeds (`robust=True`) and the video stays `pending`.
- **A stale analysis can't overwrite a new file**: the task writes with
  `UPDATE ... WHERE id = .. AND path_to_resource = <the file it analysed>`.
- **`json_analysis` is never loaded for the list** (`.defer('json_analysis')`); it can be large.
- Known issues and their planned fixes are in [`../cleanups.md`](../cleanups.md).

---

## Data flow

### Containers

```mermaid
flowchart LR
    FE["Frontend<br/>(browser, video player)"]
    subgraph docker compose
        WEB["dancing-buddy-backend<br/>Django + DRF"]
        REDIS[("redis<br/>task queue")]
        WORKER["celery-worker<br/>normalize_video_file, analyse_video"]
        DB[("db<br/>PostgreSQL")]
        MEDIA[/"backend/media/<br/>video files"/]
    end

    FE -- "HTTP /api/videos/..." --> WEB
    WEB -- "rows" --> DB
    WEB -- "save / read / delete files" --> MEDIA
    WEB -- "normalize_video_file.delay(id)" --> REDIS
    REDIS -- "next task" --> WORKER
    WORKER -- "read file" --> MEDIA
    WORKER -- "status + json_analysis" --> DB
```

Django and the worker never talk to each other directly: Redis carries only the task
message (`normalize_video_file(42)`), and the worker writes the result straight into Postgres.

### Upload → analysis → playback

```mermaid
sequenceDiagram
    autonumber
    actor U as Frontend
    participant V as views.py
    participant S as serializers.py
    participant SV as services.py
    participant DB as PostgreSQL
    participant F as media/ (disk)
    participant R as Redis
    participant W as tasks.py (worker)

    U->>V: POST /api/videos/ (title, file)
    V->>S: VideoUploadSerializer.is_valid()
    S-->>V: validated_data (or 400)
    V->>SV: upload_video(owner, title, file)
    SV->>F: save file (FileField.pre_save)
    SV->>DB: INSERT video (status pending)
    SV-->>V: video
    V-->>U: 201 video object
    Note over SV,R: after the transaction commits
    SV->>R: normalize_video_file.delay(id)

    R->>W: normalize_video_file(id), then analyse_video(id)
    W->>DB: status = processing, analysis_runs + 1
    W->>F: read file (ffprobe)
    W->>W: normalize_video() into a temp file (always re-encode, once)
    W->>F: save normalized MP4, delete the original (after commit)
    W->>DB: path, file_size, duration, is_normalized (guarded UPDATE)
    W->>W: extract_frame() + make_fitted_webp() (only if no thumbnail; a failure is just logged)
    W->>F: save thumbnail
    W->>W: run_analysis(path)
    W->>DB: status = done + json_analysis (or failed + analysis_error_code)

    loop until done or failed
        U->>V: GET /api/videos/{id}/
        V-->>U: 200 {analysis_status: ...}
    end
    U->>V: GET /api/videos/{id}/analysis/
    V-->>U: 200 json_analysis
    U->>V: GET /api/videos/{id}/stream/ (Range: bytes=...)
    V->>F: read only those bytes
    V-->>U: 206 Partial Content
```

### Inside one request (upload)

```
router → VideoViewSet.create()
       → VideoUploadSerializer(data=request.data).is_valid(raise_exception=True)
             → CharField / FileField checks → validate_file() → validate_filename(), validate_file_size()
             → invalid: ValidationError → DRF exception handler → 400
       → services.upload_video(owner=request.user, **validated_data)
             → Video.objects.create() → FileField.pre_save() → video_upload_path() → storage.save()
             → INSERT
             → transaction.on_commit(start_analysis) → normalize_video_file.delay(video.pk)
       → Response(VideoSerializer(video).data, status=201)
```
