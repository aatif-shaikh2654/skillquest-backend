# SkillQuest Backend

FastAPI backend for SkillQuest. Authentication uses HttpOnly JWT cookies set by the server. The frontend should send requests with `credentials: "include"`.

## Requirements

- Python 3.14+
- PostgreSQL
- A Google OAuth client ID (only if you use social login)
- SMTP credentials (only if you want OTP emails to send)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your database URL and a JWT secret of at least 32 characters.

Create the database and apply migrations:

```bash
createdb skillquest
python3 -m alembic upgrade head
```

Run the API:

```bash
python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
```

- API: [http://localhost:8000](http://localhost:8000)
- Health: `GET /` returns `{ "status": "ok" }` (no auth)
- Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Architecture

Layered modules: **routes → services → repositories → models**. Pydantic schemas are the API contract. Routes stay thin.

```
app/
  main.py                 FastAPI app, CORS, exception handlers
  core/                   config, JWT/cookies, email, exceptions, deps, listing pagination
  db/                     async SQLAlchemy session
  middleware/auth.py        cookie JWT middleware
  middleware/rate_limit.py  IP rate limits (on only for a public https FRONTEND_ORIGIN)
  modules/auth/           signup, OTP login, Google
  modules/user/           current user profile
  modules/instructor/     become-instructor wizard
  modules/admin/          staff login, me, logout, user listing
alembic/versions/         schema migrations
```

Protected routes read `quest_session`. Use `get_current_user` for the authenticated user and `require_admin` for staff-only routes. Public `/auth/*` and `/admin/login` / `/admin/logout` are listed in `app/middleware/auth.py`. Listing APIs use `app/core/pagination.py`: query `page`, `limit`, `search`; `data` includes `items`, `page`, `limit`, `total_count`, `total_pages`.

## Frontend contract

- Send `credentials: "include"` on every request.
- Do not store JWTs in JavaScript. Cookies are HttpOnly.
- Point `FRONTEND_ORIGIN` at the frontend origin(s), comma-separated if you have more than one (example: `http://localhost:3000, http://localhost:5173`). Cookie-setting auth POSTs (`/auth/verify-otp`, `/auth/social-login`, `/admin/login`) require a matching `Origin` (or `Referer`) header so a cross-site form cannot set session cookies.
- Call the API with the same hostname the frontend uses (`localhost` with `localhost`, or `127.0.0.1` with `127.0.0.1`). Mixed hosts are cross-site; the API then sets `SameSite=None; Secure; Partitioned` so the browser will send the cookies. Same-host requests keep `SameSite=Lax`.
- Public auth is OTP-only. Signup takes `{ email, full_name }` and creates a **USER** (`is_instructor: false`). Login takes `{ email }`. Both finish with `POST /auth/verify-otp`. After login, `POST /instructor/become` stores the wizard answers and sets `is_instructor: true`. Phone is not collected at signup. Emails are trimmed and stored/looked up in lowercase, so `Ada@Example.COM` matches `ada@example.com`.
- OTP emails are limited to one send per 60 seconds and 5 sends per 60 minutes per user. A known account that hits either limit gets `429`. Login and resend return `404` if no public account exists for that email. Signup returns `409` and does not create a row if the email is already taken.
- HTTP rate limits are **off locally**. They turn on when any `FRONTEND_ORIGIN` entry is a public `https` URL (not `localhost` / `127.0.0.1`). Auth POSTs are 10 / 60s per IP; other routes are 60 / 60s. Over the cap: `429` `{ "success": false, "message": "Too many requests. Try again later." }`. `GET /` and docs are not counted.
- `ADMIN` and `SUPER_ADMIN` sign in with `POST /admin/login` (`email` + `password`). Public signup never accepts a role or password. Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` to seed one `SUPER_ADMIN` on startup (created only if that email is new).

## Auth APIs

All routes are under `/auth`. Success body: `{ "success": true, "message": "...", "data": { ... } }`. Errors: `{ "success": false, "message": "..." }`.

Roles: `USER`, `ADMIN`, `SUPER_ADMIN`. Public signup never accepts a role from the client. Instructor is a flag (`is_instructor`), not a role.

| Method | Path                      | Auth            | Description                                                                                 |
| ------ | ------------------------- | --------------- | ------------------------------------------------------------------------------------------- |
| POST   | `/auth/signup`            | public          | `{ "email", "full_name" }` — create a **USER**, send a 6-digit OTP. `409` if email exists.  |
| POST   | `/auth/login`             | public          | `{ "email" }` — send an OTP. `404` if no account, `429` if rate-limited.                    |
| POST   | `/auth/resend-otp`        | public          | `{ "email" }` — send a new OTP. `404` if no account, `429` if rate-limited.                 |
| POST   | `/auth/verify-otp`        | public          | `{ "email", "code" }` — marks email verified and sets cookies. Staff roles cannot use this. |
| POST   | `/auth/social-login`      | public          | `{ "id_token" }` — Google ID token. New users are **USER**. Sets cookies.                   |
| POST   | `/auth/link-google`       | cookie          | `{ "id_token" }` — link Google to the logged-in user. Emails must match.                    |
| POST   | `/auth/refresh`           | `quest_renewal` | Rotate both cookies.                                                                        |
| POST   | `/auth/logout`            | cookie          | Clear cookies and invalidate sessions.                                                      |

## User APIs

| Method | Path       | Auth   | Description                                                                              |
| ------ | ---------- | ------ | ---------------------------------------------------------------------------------------- |
| GET    | `/user/me` | cookie | Return the logged-in user from the database. `401` if the session is missing or invalid. |

## Instructor APIs

Cookie-authenticated **USER** only. Completing the 4-step wizard creates an `instructors` row and sets `is_instructor: true` immediately. Staff cannot use this. `409` if already an instructor.

| Method | Path                 | Auth   | Description                                                                 |
| ------ | -------------------- | ------ | --------------------------------------------------------------------------- |
| POST   | `/instructor/become` | cookie | Wizard answers. Creates the instructor profile. `403` for staff, `409` if already set. |

### Become-instructor body

```json
{
  "teaching_experience": "ONLINE",
  "video_experience": "BEGINNER",
  "audience_size": "NONE",
  "teaching_topic": "TECHNOLOGY"
}
```

Allowed values:

- `teaching_experience`: `IN_PERSON_INFORMAL`, `IN_PERSON_PROFESSIONAL`, `ONLINE`, `OTHER`
- `video_experience`: `BEGINNER`, `SOME_KNOWLEDGE`, `EXPERIENCED`, `VIDEOS_READY`
- `audience_size`: `NONE`, `SMALL`, `SUFFICIENT`, `LARGE`
- `teaching_topic`: `TECHNOLOGY`, `DESIGN`, `BUSINESS`, `MARKETING`, `PERSONAL_DEVELOPMENT`, `MUSIC`, `HEALTH_FITNESS`, `LIFESTYLE`, `EDUCATION`, `OTHER`

### Become-instructor response `data`

User fields plus the four answers. `is_instructor` is `true`.

## Admin APIs

Staff-only. Login and logout are public paths so cookies can be set and cleared. `GET /admin/me` and `GET /admin/users` require an **ADMIN** or **SUPER_ADMIN** session (`403` for a **USER**).

| Method | Path            | Auth            | Description                                                                                          |
| ------ | --------------- | --------------- | ---------------------------------------------------------------------------------------------------- |
| POST   | `/admin/login`  | public          | `{ "email", "password" }` — **ADMIN** / **SUPER_ADMIN** only. Sets cookies.                          |
| GET    | `/admin/me`     | cookie + staff  | Return the logged-in admin from the database.                                                        |
| POST   | `/admin/logout` | cookie          | Clear cookies and invalidate the staff session. `403` if the session belongs to a **USER**.          |
| GET    | `/admin/users`  | cookie + staff  | List accounts with role **USER**. Query: `page` (default 1), `limit` (1–100, default 20), `search` (name, email, or phone). |

### Admin users list `data`

```json
{
  "items": [
    {
      "id": "uuid",
      "email": "ada@example.com",
      "full_name": "Ada Lovelace",
      "phone_number": null,
      "role": "USER",
      "is_instructor": false,
      "is_active": true,
      "email_verified": true
    }
  ],
  "page": 1,
  "limit": 20,
  "total_count": 1,
  "total_pages": 1
}
```

### Signup body

```json
{
  "email": "ada@example.com",
  "full_name": "Ada Lovelace"
}
```

### Login / verify-otp response `data`

```json
{
  "id": "uuid",
  "email": "ada@example.com",
  "full_name": "Ada Lovelace",
  "phone_number": null,
  "role": "USER",
  "is_instructor": false,
  "is_active": true,
  "email_verified": true
}
```

### Signup flow

1. `POST /auth/signup` with email and full name
2. User enters the 6-digit code from email. If no email arrives, `POST /auth/resend-otp`
3. Frontend `POST /auth/verify-otp` with `{ "email", "code" }`
4. Cookies are set; later calls use `credentials: "include"`
5. To teach, the logged-in user completes the wizard and `POST /instructor/become` with the four answers

Returning users skip signup and call `POST /auth/login` with email only, then `verify-otp`.

### OTP rate limits

Every OTP email (signup, login, resend) shares the same per-user limits:

- 60-second cooldown after the last send
- 5 sends in a rolling 60-minute window

A limited known user gets `{ "success": false, "message": "..." }` with status `429`. Login and resend return `404` (`No account found for that email.`) when the email is unknown or a staff role, and `403` (`Your account is disabled`) when the account is inactive. Signup returns `409` and does not insert a user when the email already exists.

### API rate limits

Off when every `FRONTEND_ORIGIN` entry is `http` or a local host (`localhost`, `127.0.0.1`). On when any entry is a public `https` origin. Limits are per client IP and are not configurable via env:

| Bucket | Paths                                                                                   | Default  |
| ------ | --------------------------------------------------------------------------------------- | -------- |
| Auth   | `/auth/signup`, `/login`, `/resend-otp`, `/verify-otp`, `/social-login`, `/admin/login` | 10 / 60s |
| API    | everything else except `GET /` and docs                                                 | 60 / 60s |

Over the cap: `429` `{ "success": false, "message": "Too many requests. Try again later." }`.

### Admin login

`POST /admin/login` with `{ "email", "password" }`. Only `ADMIN` and `SUPER_ADMIN`. Users cannot use this endpoint (same 401 as a bad password). After login, the admin frontend uses `GET /admin/me`, `GET /admin/users`, and `POST /admin/logout`. On first boot, if `ADMIN_EMAIL` and `ADMIN_PASSWORD` are set, the API creates that `SUPER_ADMIN` once.

### Google

The frontend obtains a Google ID token (GIS) and `POST`s it to `/auth/social-login`. The backend verifies it against `GOOGLE_CLIENT_ID`. Google is not auto-linked onto an existing verified email account — the user signs in with the email OTP, then `POST /auth/link-google`.

## Database

```bash
python3 -m alembic upgrade head
python3 -m alembic revision -m "describe the change"
```

Use Alembic for every schema change. Do not edit the database by hand in shared environments.

## Keeping docs current

When you add a feature, update this README in the same change:

1. New env vars → Environment table and `.env.example`
2. New or changed endpoints → Auth APIs (or a new section for that module)
3. Setup or run steps that changed → Quick start
4. Frontend contract changes (cookies, CORS, headers) → Frontend contract

Swagger at `/docs` is the live request/response reference. This README is the human overview.

## License

Private / unpublished.
