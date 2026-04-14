# ChoreBoard

Household chore tracker with email reminders and a web dashboard.

## Stack

- Python + Flask
- SQLite (local) / PostgreSQL (production via `DATABASE_URL`)
- APScheduler — daily job at 08:00 UTC generates assignments and sends emails
- SMTP email — works with Gmail App Passwords
- Bootstrap 5 — no build step
- Render.com — free hosting

## File Structure

```
chore_app/
├── app.py               Flask app and all routes
├── models.py            User, Chore, ChoreAssignment (SQLAlchemy)
├── scheduler.py         APScheduler: generate assignments + send reminders
├── email_service.py     SMTP email sender (grouped per user)
├── init_db.py           First-run: creates tables and first admin account
├── run.sh               Local run script
├── requirements.txt
├── render.yaml          Render.com deployment config
├── .env.example         Environment variable template
└── templates/
    ├── base.html
    ├── setup.html       First-time admin creation (shown when no users exist)
    ├── login.html
    ├── dashboard.html   Stats, overdue, today, upcoming 7 days
    ├── chores_list.html
    ├── chore_form.html  Frequency + assignment form with JS show/hide
    ├── members_list.html
    └── member_form.html
```

## Data Models

**User** — `id, name, email, password_hash, is_admin`

**Chore** — `id, name, description, frequency_type, frequency_value, assignment_type, assigned_user_id, last_assigned_user_id, active`
- `frequency_type`: `daily` | `weekly` | `custom`
- `frequency_value`: weekday list `"0,2,4"` (weekly) or interval `"14"` (custom)
- `assignment_type`: `round_robin` | `specific`

**ChoreAssignment** — `id, chore_id, user_id, due_date, completed_at, reminder_sent`

## Routes

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| GET/POST | `/setup` | public | First-time admin setup |
| GET/POST | `/login` | public | Login |
| GET | `/logout` | auth | Logout |
| GET | `/` | auth | Dashboard |
| POST | `/assignments/<id>/complete` | auth | Mark done |
| POST | `/assignments/<id>/uncomplete` | auth | Undo done |
| GET | `/chores` | auth | Chore list |
| GET/POST | `/chores/new` | admin | Add chore |
| GET/POST | `/chores/<id>/edit` | admin | Edit chore |
| POST | `/chores/<id>/delete` | admin | Deactivate chore |
| GET | `/members` | admin | Member list |
| GET/POST | `/members/new` | admin | Add member |
| GET/POST | `/members/<id>/edit` | admin | Edit member |
| POST | `/members/<id>/delete` | admin | Remove member |
| POST | `/admin/generate-assignments` | admin | Run scheduler now |
| POST | `/admin/send-reminders` | admin | Send emails now |

## Running Locally

```bash
./run.sh
```

The script will:
1. Create a Python virtual environment
2. Install dependencies
3. Copy `.env.example` to `.env` on first run (fill in your values, then re-run)
4. Run `init_db.py` to create tables and first admin account (if no DB exists)
5. Start the Flask dev server at http://localhost:5000

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | yes | dev fallback | Flask session secret |
| `DATABASE_URL` | no | SQLite `chores.db` | PostgreSQL URL for production |
| `APP_URL` | yes | `http://localhost:5000` | Public URL (used in email links) |
| `SMTP_HOST` | no | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | no | `587` | SMTP port (STARTTLS) |
| `SMTP_USER` | yes | — | Gmail address |
| `SMTP_PASSWORD` | yes | — | Gmail App Password |
| `EMAIL_FROM` | no | `SMTP_USER` | From header |

### Gmail App Password

1. Enable 2-Step Verification on your Google account
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Generate → paste as `SMTP_PASSWORD`

## Deploying to Render.com

1. Push the repo to GitHub
2. New Web Service → connect repo (Render auto-detects `render.yaml`)
3. Set secret env vars in the Render dashboard: `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `APP_URL`
4. Deploy — visit `/setup` on first load to create the admin account

> **SQLite on Render free tier:** data is wiped on every redeploy.
> Options: enable a Render Persistent Disk, or point `DATABASE_URL` at a free
> PostgreSQL (Supabase, Railway, or Render's own Postgres free tier).

## How the Scheduler Works

Runs daily at **08:00 UTC**:

1. **generate_assignments** — for each active chore, checks if it's due today:
   - `daily` → always
   - `weekly` → if today's weekday is in the chore's day list
   - `custom` → if enough days have passed since the last assignment
   - Picks the next user (round-robin or specific), creates a `ChoreAssignment` row

2. **send_due_reminders** — finds all unsent, incomplete assignments due today, groups them by user, sends one email per user

Admin users can also trigger both steps manually from the dashboard.
