# API contract decisions (DAN-146)

Base: `docs/openapi.yaml` on `chore/DAN-146-api-specification` (with DAN-101 merged).
Compared with: `backend/db/diagram/v2.md` and the current backend code.
The spec was rewritten from this log on 2026-11-09; the log is the source of truth for why.
Last updated: 2026-11-09.

## Legend

**Origin**: where the point comes from

| Mark | Meaning |
|---|---|
| 🆕 **New** | only in the OpenAPI spec, not in our assumptions (v2 / code) |
| 🗂️ **Old** | already in v2 or in the code |
| ➕ **Added** | in neither; came up during this review |

**Status**

| Mark | Meaning |
|---|---|
| 🟢 **Decided** | accepted as proposed |
| 🟡 **Corrected** | the original (spec or v2) was changed; the change is shown as ~~old~~ → **new** |
| 🔴 **Rejected** | the original idea was dropped; what was dropped is highlighted |
| ⚪ **Pending** | not decided yet; a recommendation or fix is given |
| ⚠️ | an open hook: something still unfixed or something to watch, listed at the bottom of a point |

## Summary

| ID | Topic | Origin | Status |
|---|---|---|---|
| D0.1 | `/api/videos/` vs `/api/library/` + scope toggle | 🗂️ | 🟡 ⚠️ |
| D0.2 | Instructor role | 🆕 | 🔴 |
| D1.1 | Login identifier | 🆕 | 🟡 |
| D1.2 | Rate limiting | 🆕 | 🟢 ⚠️ |
| D1.3 | Login/register response | 🆕 | 🟡 ⚠️ |
| D1.4 | CSRF bootstrap | ➕ | 🟢 ⚠️ |
| D1.5 | Register logs in | ➕ | 🟢 |
| D1.6 | Password rules | 🆕 | 🟡 |
| D1.7 | Password reset (recovery code) | ➕ | 🟢 ⚠️ |
| D2.1 | Profile fields | 🗂️ | 🟡 |
| D2.2 | Public profile | ➕ | 🟢 ⚠️ |
| D2.3 | `/me` endpoints | 🆕 | 🟡 ⚠️ |
| D2.4 | Avatar rules | 🗂️ | 🟡 ⚠️ |
| D2.5 | Avatar field name in code | ➕ | 🟢 ⚠️ |
| D3.1 | Song info | 🆕 | 🟡 |
| D3.2 | Difficulty | 🗂️ | 🟡 |
| D3.3 | Owner sees processing data | 🗂️ | 🟡 |
| D3.4 | Formats + video normalization | 🗂️ | 🟡 ⚠️ |
| D3.5 | Thumbnail | 🗂️ | 🟡 ⚠️ |
| D3.6 | Replacing the file | 🗂️ | 🔴 ⚠️ |
| D3.7 | Re-run failed analysis | ➕ | 🟢 |
| D4.1 | Publish / unpublish | 🗂️ | 🟢 |
| D4.2 | Library search and filters | 🆕 | 🟡 ⚠️ |
| D4.3 | `times_played` | 🆕 | 🟡 ⚠️ |
| D4.4 | Access to public videos | 🗂️ | 🟡 ⚠️ |
| D5.1 | Like endpoints + computed counts | 🗂️ | 🟡 ⚠️ |
| D5.2 | Like rules + liked list | 🗂️ | 🟡 ⚠️ |
| D6.1 | Creating an attempt | 🗂️ | 🟢 ⚠️ |
| D6.2 | Attempt fields + score | 🗂️ | 🟡 ⚠️ |
| D6.3 | Score difference | 🆕 | 🟡 |
| D6.4 | Attempt history | 🆕 | 🟡 |
| D6.5 | Who can dance which video | 🗂️ | 🟢 |
| D6.6 | Attempt only on an analysed video | ➕ | 🟢 |
| D6.7 | Keeping the attempt recording | ➕ | 🟢 ⚠️ |
| D6.8 | Deleting an attempt | 🆕 | 🟢 ⚠️ |
| D7.1 | JSON naming | 🆕 | 🟡 ⚠️ |
| D7.2 | IDs | 🆕 | 🟡 |
| D7.3 | Pagination | ➕ | 🟢 ⚠️ |
| D7.4 | Analysis JSON format | 🗂️ | 🟢 ⚠️ |
| D7.5 | Error format | 🗂️ | 🟡 |
| D7.6 | Access without logging in | ➕ | ⚪ |

---

## 0. Structure

### 🟡 D0.1 🗂️ What `/api/videos/` and `/api/library/` are
**Point:** the spec says `GET /api/videos/` returns "the authenticated user's videos", but gives it library-style
filters. v2 splits my videos and the public library. The UI has a **toggle** on the browse screen:
"public + mine" ↔ "mine only". Building "public + mine" on the client from two APIs doesn't work: two paginated,
sorted infinite-scroll lists can't be merged correctly (the order breaks, items repeat, and one list mixes two DTO shapes).

**Solution:**
- **Browse** = `GET /api/library/?scope=all|mine` (default `all`)
  - `all` = public videos **+ all my own** (including private) · `mine` = only my own
  - one DTO for every card; it adds `is_mine` and `visibility`, so my private videos get a "private" badge
  - the toggle only changes `scope`; filters, ordering and pagination stay the same (D4.2, D7.3)
  - `GET /api/library/{id}/` works for public videos and for my own (any visibility)
- **Manage** = `GET /api/videos/` (my uploads: status, upload, edit, publish), with the **same shared filter set** as the
  library + `?analysis_status=` and `?visibility=`
- one shared DRF `FilterSet` (search, difficulty, author, ordering) used by both endpoints

**Change:** ~~v2 "library = only public videos"~~ → **library = what I can dance: public + mine, with a `scope` toggle**;
~~filters only on the library~~ → **the same filters on both endpoints**.

⚠️ Ordering "newest" sorts by `published_at`, which is null for private videos: use `COALESCE(published_at, created_at)`.
⚠️ My private cards must hide the like button (likes only on public videos, D5.1).
⚠️ `scope=all` is a `visibility = 'public' OR owner = me` query, which can't use the v2 `(visibility, published_at)` index
fully. That's fine at our size; revisit if the library gets slow.

### 🔴 D0.2 🆕 Instructor role
**Point:** the spec adds `/api/instructor/videos/` and `/api/instructor/videos/{id}/` with 403 for non-instructors;
v2 has no roles.

**Solution:** no role. Every user can upload and publish. `/api/videos/` already is the "instructor view".

**Rejected:** ~~instructor role~~, ~~`/api/instructor/videos/`~~, ~~`/api/instructor/videos/{id}/`~~,
~~`InstructorVideoDetailsDto`~~, ~~403 "not an instructor"~~.

---

## 1. Auth

### 🟡 D1.1 🆕 Login identifier
**Point:** the spec signs in with a separate `login` field; v2 has `email`. The team doesn't want email verification / SMTP.

**Solution:** private `login` (unique, used only to sign in) + public `username` (unique, shown everywhere). No email.

**Change:** ~~v2 `USER.email`~~ → **`USER.login`**; password reset without email → **recovery code (D1.7)**.

**Rejected:** ~~an unverified email used as a "secret phrase" for reset~~: emails are often public or guessable, so
anyone who knows login + email could take over the account.

### 🟢 D1.2 🆕 Rate limiting
**Point:** the spec lists 429 on login/register.

**Solution:** DRF `ScopedRateThrottle` per IP: login 5/min, register 3/min, password reset 5/min (tune later) → 429 with `Retry-After`.

⚠️ Behind Docker / a reverse proxy every request may come from the proxy IP, so all users would share one limit.
Set `NUM_PROXIES` so the IP is read from `X-Forwarded-For`.

### 🟡 D1.3 🆕 Login / register response
**Point:** the spec's login and register return no body, so the frontend needs an extra `GET /me`.

**Solution:** login → 200 `CurrentUser`, register → 201 `CurrentUser` + `recovery_code` (D1.7). Logout → 204.

**Change:** ~~empty body~~ → **`CurrentUser`**.

⚠️ Auth isn't implemented yet. The frontend still uses DRF's `/api-auth/` and **hardcoded basic-auth credentials**
(`REACT_APP_USERNAME/PASSWORD` in `frontend/src/api/axios_instances.js`). Remove them when the real auth lands.

### 🟢 D1.4 ➕ CSRF bootstrap
**Point:** session auth needs a `csrftoken` cookie before the first POST; the spec didn't say how to get it.

**Solution:** `GET /api/auth/csrf/` → 204 + `csrftoken` cookie. Every POST/PATCH/PUT/DELETE sends `X-CSRFToken`
(documented in the security section of the spec).

⚠️ Django rotates the CSRF token on login, so the frontend must re-read the cookie afterwards.
For the React dev server on another origin, set `CSRF_TRUSTED_ORIGINS`, CORS with credentials and
the `SameSite` cookie settings, or requests fail with 403.

### 🟢 D1.5 ➕ Register logs in
**Point:** whether a separate login call is needed after register.

**Solution:** register sets the session cookie; the user is logged in right away.

### 🟡 D1.6 🆕 Password rules
**Point:** the spec has min 12 / **max 32** and validates lengths on the login request too.

**Solution:** Django `AUTH_PASSWORD_VALIDATORS` (similar to username/login, min length, common passwords, only digits),
max 128 → 400 field errors. The login request has no rules; wrong credentials → 401.

**Change:** ~~length 12–32, also checked on login~~ → **Django validators, max 128, no rules on login**.

### 🟢 D1.7 ➕ Password reset with a recovery code
**Point:** users must be able to reset a forgotten password, but there's no email / SMTP (D1.1).

**Solution:** a one-time **recovery code**, like 2FA backup codes:
- on register the 201 response contains `recovery_code` **once**, next to `CurrentUser`; the frontend makes the user save it
- the code is random (e.g. 16 characters, ~80 bits) and stored only as a hash (`make_password`)
- `POST /api/auth/password-reset/` `{login, recovery_code, new_password}` → 200 `{recovery_code}` (a **new** code; the old one is used up)
- `POST /api/users/me/recovery-code/` `{password}` → 200 `{recovery_code}`: a logged-in user generates a new code
- a wrong login or code gives the same 400 `{detail: "Invalid login or recovery code."}`, so it doesn't reveal which logins exist
- rate-limited like login (D1.2)

⚠️ A user who loses both the password and the recovery code can only be helped by an admin.
⚠️ A reset should end the user's other sessions (log out other devices).
⚠️ v2 needs `USER.recovery_code_hash` (see the v2 follow-ups at the end).

---

## 2. User

### 🟡 D2.1 🗂️ Profile fields
**Point:** the spec has `username`, `login`, `avatarUrl`; v2 has `username`, `email`, `display_name`, `avatar`, `bio`.

**Solution:** `username` (public, also the display name), `login` (private), `avatar_url` (nullable), `bio` (max 300, may be empty).

**Change:** ~~`display_name`~~ (same as username) and ~~`email`~~ (D1.1) → **removed**; **`bio` added to the spec**.

### 🟢 D2.2 ➕ Public profile
**Point:** videos show the author, but there was no page for the author.

**Solution:** `GET /api/users/{username}/` → `{username, avatar_url, bio, public_videos_count}` (never `login`);
their videos via `GET /api/library/?author=<username>`; unknown username → 404.

⚠️ The username `me` must be reserved (see D2.3).

### 🟡 D2.3 🆕 `/me` endpoints
**Point:** the spec uses verb-style URLs: `/me/edit-login/`, `/me/edit-password/`, `/me/delete/`.

**Solution:**
- `GET /api/users/me/`, `PATCH /api/users/me/` (username, bio, avatar; multipart)
- `PATCH /api/users/me/login/` (`login` + `password`)
- `POST /api/users/me/password/` (`old_password`, `new_password`) → 204
- `DELETE /api/users/me/` (`password` in the body) → 204
- `DELETE /api/users/me/avatar/` → 204

**Change:** ~~`edit-login/`, `edit-password/` (returned the user), `delete/`~~ → **resource URLs above**.

⚠️ `/api/users/me/` and `/api/users/{username}/` share a path, so the username `me` must be rejected on register and rename.
⚠️ After a password change call `update_session_auth_hash`, otherwise the user is logged out.
⚠️ `DELETE /api/users/me/` carries the password in the request body. That's allowed, but OpenAPI 3.0 tools
(Swagger UI) and some proxies ignore DELETE bodies. If that becomes a problem, use `POST /api/users/me/delete/` instead.
A wrong password confirmation (login change, password change, account delete, new recovery code) → 403 `{detail}`.

### 🟡 D2.4 🗂️ Avatar rules
**Point:** the spec has `avatarUrl` as required, with no size limit and no way to remove it; v2 says null = default avatar.

**Solution:** `avatar_url` nullable (the frontend shows the default); upload field `avatar`, JPEG/PNG, max 5 MB;
removed via `DELETE /api/users/me/avatar/`.

**Change:** ~~required, unlimited~~ → **nullable, max 5 MB, removable**.

⚠️ The code field is named differently (D2.5).

### 🟢 D2.5 ➕ Avatar field name in code
**Point:** the spec says `avatar_url`, v2 says `avatar`, DAN-101 code says `User.thumbnail` (`accounts/migrations/0002_user_thumbnail.py`).

**Solution:** the naming convention is **`avatar`** (model field `avatar`, API field `avatar_url`, upload field `avatar`).
The code is renamed later, not in this task.

⚠️ Until the rename, `User.thumbnail` and `Video.thumbnail` share a name but mean different things. Once
`0002_user_thumbnail` is on `main`, the rename needs its own `RenameField` migration.

---

## 3. My videos

### 🟡 D3.1 🆕 Song info
**Point:** the spec added `songTitle` / `songArtist`, which weren't in v2.

**Solution (implemented in DAN-101):** `song_title` and `song_author`, max 200, typed by the user, optional (may be empty),
on upload and PATCH.

**Change:** ~~`songArtist`~~ → **`song_author`** (code name, snake_case).

### 🟡 D3.2 🗂️ Difficulty
**Point:** the spec has 5 levels with spaces (`very easy` … `very hard`), required everywhere; v2 has 3 levels, null until set.

**Solution:** `beginner | intermediate | advanced`, null until set, chosen by the author on upload / PATCH,
required to publish. One shared `Difficulty` schema in the spec.

**Change:** ~~5 levels with spaces, always required~~ → **3 levels (v2), nullable**.

### 🟡 D3.3 🗂️ What the owner sees about processing
**Point:** the spec removed `analysis_status` from the video DTO (only the instructor DTO had it), but the frontend polls it.

**Solution:** the "my video" DTO = DAN-101 `VideoSerializer`: `id, title, description, song_title, song_author,
difficulty, file_size, duration_seconds, analysis_status, visibility, published_at, likes_count, created_at,
updated_at` + `thumbnail_url` + `best_score` (D6.4).

**Change:** ~~`analysis_status` only for instructors~~ → **every owner sees status and file facts**.

### 🟡 D3.4 🗂️ Accepted formats and video normalization
**Point:** the spec allowed MP4 only, on the assumption that the analysis model needs it. The code accepts `mp4, mov, webm`.

**Findings:** MediaPipe never reads files; OpenCV (`VideoCapture`) and Essentia decode them with FFmpeg, so all three
formats work. The real problems are browser webm (missing frame count), wrong timing for non-30 fps videos, and iPhone
HEVC not playing in Chrome/Firefox.

**Solution:** accept `mp4, mov, webm`, max 500 MB, for videos and attempt recordings. The server **normalizes** every
upload to H.264/AAC MP4, constant 30 fps, **max 1080p** before the analysis. The stored file is always MP4.
Normalization is a **separate task outside the API**; the spec only mentions it in descriptions (upload,
`/stream/` serves `video/mp4` only, `analysis_status: failed` includes a failed normalization).

**Change:** ~~MP4 only~~ → **mp4 / mov / webm + server-side normalization**.

⚠️ Normalization isn't implemented yet.
⚠️ Analysis bugs, unfixed: `video_analysis/initial_analysis.py:233` divides by the frame count (0 for browser webm →
ZeroDivisionError); `:210` labels 25/50 fps frames as 30 fps (≈20 % drift vs. the music). Normalization to 30 fps
CFR hides both, but the code should still be fixed.

### 🟡 D3.5 🗂️ Thumbnail
**Point:** v2 has a `thumbnail` path; the spec has `thumbnailUrl` (required); the code has a `/thumbnail/` endpoint returning 501.

**Solution:** `thumbnail_url` (nullable) in the my-video, library and `reference_video` DTOs; the frontend shows a placeholder
while it's null. The `/thumbnail/` endpoint is removed. Generation is a separate task (mentioned in the field description).

**Change:** ~~`/thumbnail/` endpoint~~, ~~required~~ → **nullable `thumbnail_url` field**.

⚠️ Still in code: the `thumbnail` action in `backend/videos/views.py` (501) and `video_thumbnail` in
`frontend/src/api/endpoints.js`. `thumbnail` isn't in `VideoSerializer` yet. Generation isn't implemented.

### 🔴 D3.6 🗂️ Replacing the video file
**Point:** the spec (and the old code) let PATCH replace the file and re-run the analysis. That's risky for public videos with attempts and likes.

**Solution (implemented in DAN-101):** the file can't be replaced; PATCH with `file` → 400; delete and upload again.
PATCH is JSON only.

**Rejected:** ~~replacing the file via PATCH~~, ~~multipart PATCH~~, ~~`file` in `VideoUpdateRequest`~~.

⚠️ The spec still documents multipart PATCH and the `file` field in `VideoUpdateRequest`; remove them in the spec rewrite.

### 🟢 D3.7 ➕ Re-run a failed analysis
**Point:** v2 says a failed analysis "can be re-run", but there was no endpoint.

**Solution:** `POST /api/videos/{id}/reanalyze/` and `POST /api/dance-attempts/{id}/reanalyze/`, owner only →
202 with the DTO (`pending`); only when the status is `failed`, else 409.

---

## 4. Library

### 🟢 D4.1 🗂️ Publish / unpublish
**Point:** the spec had no visibility at all; v2 has `visibility` + `published_at`.

**Solution (implemented in DAN-101):** `visibility` in the PATCH body. Publishing → 409 if the video isn't analysed or has
no difficulty. Unpublishing clears `published_at` and keeps the likes.

### 🟡 D4.2 🆕 Library search and filters
**Point:** the spec has separate filters per field, including song fields that users type freely (not validated).

**Solution:** `GET /api/library/` and `GET /api/library/{id}/`:
- `?search=`: case-insensitive partial match over title, song title, song author, author username
- filters only on validated values: `?difficulty=`, `?author=` (exact username)
- `?ordering=newest|likes|played` (default `newest`); paginated (D7.3)
- library DTO = public fields + `author_username`, `author_avatar_url`, `liked_by_me`, `best_score`, `times_played`

**Change:** ~~`title`, `songTitle`, `songArtist`, `authorUsername` filters~~ → **one `search` + `difficulty` + `author`**.
More filters (e.g. dance style, BPM from audio analysis) can be added later as optional params without breaking the contract.

⚠️ `ordering=likes` / `ordering=played` sort by counts computed per request (D4.3, D5.1), not by stored columns.

### 🟡 D4.3 🆕 `times_played`
**Point:** the spec added a play counter without saying what a "play" is.

**Solution:** `times_played` = number of dance attempts on the video, **counted per request**
(`annotate(times_played=Count('dance_attempts'))`), with no stored column. It counts the attempts that **exist now**:
deleting an attempt (D6.8) or an account lowers it.

**Change:** ~~stored counter `VIDEO.times_played` with `F() + 1`~~ → **computed from DANCE_ATTEMPT**.

⚠️ Deleted attempts are hard-deleted (D6.8) and deleting a user account deletes their attempts (CASCADE), so counts on
other people's videos can go down. That's accepted.
⚠️ The count needs an index on `DANCE_ATTEMPT.reference_video_id`. The v2 index `(user_id, reference_video_id)` starts
with `user_id`, so it doesn't help here.

### 🟡 D4.4 🗂️ Access to public videos
**Point:** the code is owner-only (`get_video()` filters by `owner`), but the library and attempts need others to stream
public videos and get their analysis.

**Solution:** all read actions (`GET /api/videos/{id}/`, `/stream/`, `/analysis/`, `/dance-attempts/`): owner **or** public video.
PATCH / DELETE / reanalyze: owner only. Someone else's private video → 404.
A non-owner reading `GET /api/videos/{id}/` gets the **public subset**: owner-only fields (`file_size`, `analysis_status`,
`updated_at`) are hidden by the serializer. So the spec has two DTOs: `PublicVideo` (the library DTO) and
`MyVideo` = `PublicVideo` + the owner-only fields. `visibility` stays in `PublicVideo` (always `public` for other people's
videos), because the library needs it for the "private" badge on my own videos (D0.1).

**Change:** ~~owner-only everything~~ → **owner or public for read actions, with owner-only fields hidden from others**.

⚠️ `get_video()` in `backend/videos/views.py` still filters by owner.
⚠️ A public video now has two detail URLs: `GET /api/videos/{id}/` and `GET /api/library/{id}/`. They must return the same
`PublicVideo` shape for non-owners. The frontend should pick one (`/api/library/{id}/` for the library page) so the
two don't drift apart.

---

## 5. Likes

### 🟡 D5.1 🗂️ Like endpoints
**Point:** the spec had `likesCount`, but no way to like and no `likedByMe`. v2 stores `likes_count` on VIDEO and keeps it
in sync with VIDEO_LIKE.

**Solution:**
- `PUT /api/library/{id}/like/` and `DELETE /api/library/{id}/like/`, idempotent → 200 `{likes_count, liked_by_me}`;
  liking a video that isn't public → 404
- everything is based on **VIDEO_LIKE**: `likes_count` = `COUNT(VIDEO_LIKE)` and `liked_by_me` = `EXISTS(VIDEO_LIKE for me)`,
  both **computed per request** (`annotate`), with no stored counter
- `likes_count` and `liked_by_me` in library DTOs; `likes_count` in my-video DTOs

**Change:** ~~stored `VIDEO.likes_count` kept in sync with `F() ± 1`~~ → **computed from VIDEO_LIKE**.

⚠️ The VIDEO_LIKE model isn't implemented.
⚠️ DAN-101 already added the `Video.likes_count` column, its `>= 0` check constraint and the `video_library_likes_idx` index.
Drop all three in a migration, and drop the v2 rule "`likes_count` changes only together with a VIDEO_LIKE insert/delete".

### 🟡 D5.2 🗂️ Like rules and the liked list
**Point:** v2 asked whether own videos can be liked and whether there's a "liked videos" list.

**Solution:**
- own videos can be liked; likes only on library videos, not on attempts
- **`GET /api/library/liked/`**: the videos I liked that are **public or mine**, newest like first (`VIDEO_LIKE.created_at`);
  the same filters, search and pagination as the library (D4.2, D7.3)
- a liked video that its owner unpublished keeps the like (v2 rule) but disappears from my list until it's public again

**Change:** ~~no "liked videos" list~~ → **`GET /api/library/liked/`**.

⚠️ `/api/library/liked/` and `/api/library/{id}/` share a path. This works only because `{id}` accepts digits only
(`lookup_value_regex = r'\d+'`), so keep that regex on the library viewset.

---

## 6. Dance attempts

### 🟢 D6.1 🗂️ Creating an attempt
**Point:** the spec had no POST; v2 left "upload vs live analysis" open.

**Solution:** `POST /api/dance-attempts/` multipart (`reference_video_id`, `recording`) → 201 with `status: pending`;
analysed in the background like videos (pending → processing → done / failed); the frontend polls `GET /api/dance-attempts/{id}/`.

⚠️ DANCE_ATTEMPT isn't implemented (no model, no views). Update the v2 open question to "upload".

### 🟡 D6.2 🗂️ Attempt fields and score
**Point:** the spec has an integer score with per-frame details and no status / reference video; v2 has a float score with per segment/joint details.

**Solution:** `id`, `status`, `score` (int 0–100, null until done), `score_details` (per segment / joint, null until done),
`score_diff_previous`, `score_diff_best` (D6.3), `reference_video: {id, title, thumbnail_url} | null` (null if the video was deleted),
`reference_title` (kept as a fallback), `created_at`. No `recording_url` (no replay for now).

**Change:** ~~`attemptOverallScore` / float~~ → **`score` int**; ~~`detailedFramesScores` per frame~~ → **`score_details` per segment / joint**;
**`status` and `reference_video` added**.

⚠️ The `score_details` structure depends on the scoring algorithm, which doesn't exist yet; mark it `x-unstable` like D7.4.

### 🟡 D6.3 🆕 Score difference
**Point:** the spec has one `lastAttemptScoreDifference` without saying what it compares to.

**Solution:** two fields, computed on read: `score_diff_previous` (vs. my previous attempt on the same video) and
`score_diff_best` (vs. my best earlier score on it). Null for the first attempt or while not done.

**Change:** ~~`lastAttemptScoreDifference`~~ → **`score_diff_previous` + `score_diff_best`**.

⚠️ Because the diffs are computed on read, deleting an attempt (D6.8) changes the diffs of later attempts, and deleting
my best attempt lowers `best_score` on the video. That's expected: the history only shows attempts that still exist.

### 🟡 D6.4 🆕 Attempt history
**Point:** the spec makes `videoId` **required** on `GET /api/dance-attempts/`, so there's no full history.

**Solution:**
- `GET /api/dance-attempts/`: my full history, paginated, newest first, optional `?video_id=`
- `GET /api/videos/{id}/dance-attempts/`: my attempts on one video (own or public video, else 404)
- `GET /api/dance-attempts/{id}/` and `DELETE /api/dance-attempts/{id}/` (D6.8)
- `best_score` (my best on that video, null if none) in my-video and library DTOs

**Change:** ~~required `videoId`~~ → **optional filter + nested per-video URL**
(~~`/dance-attempts/{video_id}/`~~ rejected, because it clashes with `/dance-attempts/{attempt_id}/`).

### 🟢 D6.5 🗂️ Who can dance which video
**Point:** v2 rule: the reference video must be public or owned by the dancer.

**Solution:** confirmed; otherwise → 404.

### 🟢 D6.6 ➕ Attempt only on an analysed video
**Point:** scoring compares against the reference video's analysis, which exists only when `analysis_status = done`.
Own private videos can still be pending or failed.

**Solution:** `POST /api/dance-attempts/` → 409 `{detail}` if the reference video isn't `done`.
The frontend hides the "Dance" button until then.

### 🟢 D6.7 ➕ Keeping the attempt recording
**Point:** v2 has `recording` ("null if not saved"). D6.2 dropped replay for now, so the question was whether the file is
still needed after scoring.

**Solution:** recordings are **always kept** (normalized MP4, D3.4). That leaves room for a replay feature later
(`recording_url` + a stream endpoint, added without breaking the contract) and lets reanalyze (D3.7) work.

⚠️ Storage grows with every attempt (up to 500 MB per upload before normalization). Watch the disk usage and plan a
retention or cleanup policy if it becomes a problem.
⚠️ The recording file must be deleted together with its attempt (D6.8) and with the user account
(`post_delete` signals, as for videos in `cleanups.md`).

### 🟢 D6.8 🆕 Deleting an attempt
**Point:** the spec has `DELETE /api/dance-attempts/{id}/`. It was first rejected so that `times_played` would never go down,
then the decision was reversed (2026-11-10): users can delete their attempts.

**Solution:**
- `DELETE /api/dance-attempts/{id}/` → 204; owner only, someone else's attempt → 404
- **hard delete**: the row and the recording file are removed; `times_played` (D4.3), `best_score` and the score diffs
  (D6.3) are recomputed from the attempts that are left
- allowed in **any status**, also while `pending` / `processing`

⚠️ A background scoring task may still be running for a deleted attempt. It must check that the attempt still exists before
writing the result and quietly stop if not (same pattern as `services.set_analysis_result` for videos).
⚠️ Deleting the file while the task reads it: the task must also handle a missing file (end without an error, no `failed` write).

---

## 7. Conventions

### 🟡 D7.1 🆕 JSON naming
**Point:** the spec mixes camelCase (`videoId`, `authorUsername`) and snake_case (`created_at`, `old_password`).

**Solution:** snake_case everywhere (JSON keys and query params), which is the DRF default and needs no extra library.

**Change:** ~~camelCase fields~~ → **snake_case** (`authorUsername` → `author_username`, …).

⚠️ Check the frontend (`frontend/src`) for camelCase keys when the spec is applied.

### 🟡 D7.2 🆕 IDs
**Point:** the spec uses `videoId`, `userId`, `attemptId`; the code uses `id`.

**Solution:** `id` on every object; references are `<thing>_id` (`reference_video_id`, `?video_id=`).

**Change:** ~~`videoId` / `userId` / `attemptId`~~ → **`id`**.

### 🟢 D7.3 ➕ Pagination
**Point:** no list in the spec was paginated; the library will use infinite scroll.

**Solution:** `LimitOffsetPagination` on every list (`?limit=&offset=` → `{count, next, previous, results}`, default
`limit` 20, max 100); infinite scroll follows `next`. Cursor pagination was rejected because it can't sort by likes.

⚠️ Breaking change for the current frontend video list, which expects a plain array; it must read `results`.

### 🟢 D7.4 🗂️ Analysis JSON format
**Point:** the analysis format isn't settled (list of frames vs. ChoreoData, DAN-35).

**Solution:** documented as an object marked `x-unstable: true`; a separate task defines the schema after DAN-35.

⚠️ The frontend skeleton overlay depends on this format; agree on it before building that view.

### 🟡 D7.5 🗂️ Error format
**Point:** the spec uses `{detail}` and field errors but skips 401 on most operations and 416 on stream.

**Solution:** DRF default: `{detail}` for general errors and `{field: [messages]}` for validation; 401 on every secured
operation; `/stream/` documents 206 + `Content-Range` and 416.

**Change:** ~~409 "username or login already exists"~~ → **400 field error** (DRF's unique validators do that by default).

### ⚪ D7.6 ➕ Access without logging in
**Point:** the rewritten spec requires a session on every endpoint except register, login, CSRF and password reset.
Nobody decided whether a visitor can browse the library before signing up.

**Recommendation:** keep login required everywhere for now (simplest, and the library mixes in my own videos anyway).
If a public landing page is wanted later, open `GET /api/library/` (`scope=all` = public only for anonymous visitors),
`GET /api/library/{id}/` and `/stream/` to anonymous users; `liked_by_me`, `best_score` and `is_mine` are then `false` / `null`.

---

## Follow-ups for data model v2 (`backend/db/diagram/v2.md`)

| Change | From |
|---|---|
| `USER.email` → `USER.login` (unique) | D1.1 |
| add `USER.recovery_code_hash` (string, hashed one-time code) | D1.7 |
| "The library" section: library = public + my own videos (`scope=all|mine`), not only public | D0.1 |
| drop `USER.display_name` | D2.1 |
| keep `USER.avatar` (convention); rename the code field `User.thumbnail` → `avatar` later | D2.5 |
| no `VIDEO.times_played` column: computed as `COUNT(DANCE_ATTEMPT)`; add an index on `DANCE_ATTEMPT.reference_video_id` | D4.3 |
| drop `VIDEO.likes_count` (+ its constraint, index and sync rule): computed as `COUNT(VIDEO_LIKE)` | D5.1 |
| "The library" section: add the liked list (`/api/library/liked/`) | D5.2 |
| DANCE_ATTEMPT can be deleted by its owner (hard delete, recording file removed via `post_delete`) | D6.8 |
| `DANCE_ATTEMPT.score` int 0–100 (was float) | D6.2 |
| `DANCE_ATTEMPT.score_details` per segment / joint | D6.2 |
| answer the open questions: upload (not live), own videos can be liked | D5.2, D6.1 |
| rule: attempt only on a reference video with `analysis_status = done` | D6.6 |
| `DANCE_ATTEMPT.recording` always kept (not null after upload) | D6.7 |
