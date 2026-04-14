"""
Daily scheduler — runs at 08:00 every morning:
  1. generate_assignments: create ChoreAssignment rows for chores due today
  2. send_reminders: email each user their due chores (grouped into one email)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler

from email_service import send_reminders as email_send_reminders
from models import ChoreAssignment, Chore, User, db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_chore_due(chore: Chore, target: date) -> bool:
    if chore.frequency_type == 'daily':
        return True

    if chore.frequency_type == 'weekly':
        if not chore.frequency_value:
            return False
        days = [int(d) for d in chore.frequency_value.split(',') if d]
        return target.weekday() in days

    if chore.frequency_type == 'custom':
        interval = int(chore.frequency_value or 1)
        last = (
            ChoreAssignment.query
            .filter_by(chore_id=chore.id)
            .order_by(ChoreAssignment.due_date.desc())
            .first()
        )
        if last is None:
            return True
        return (target - last.due_date).days >= interval

    return False


def _next_round_robin_user(chore: Chore) -> User | None:
    users = User.query.order_by(User.id).all()
    if not users:
        return None
    if chore.last_assigned_user_id is None:
        return users[0]
    ids = [u.id for u in users]
    try:
        idx = ids.index(chore.last_assigned_user_id)
        return users[(idx + 1) % len(users)]
    except ValueError:
        return users[0]


# ---------------------------------------------------------------------------
# Core jobs
# ---------------------------------------------------------------------------

def generate_assignments(app, target: date | None = None) -> int:
    """Create assignment rows for all chores due on *target* (default: today).
    Returns the number of new assignments created."""
    with app.app_context():
        target = target or date.today()
        created = 0

        for chore in Chore.query.filter_by(active=True).all():
            if not _is_chore_due(chore, target):
                continue

            exists = ChoreAssignment.query.filter_by(
                chore_id=chore.id, due_date=target
            ).first()
            if exists:
                continue

            if chore.assignment_type == 'specific':
                user = User.query.get(chore.assigned_user_id)
            else:
                user = _next_round_robin_user(chore)
                if user:
                    chore.last_assigned_user_id = user.id

            if user:
                db.session.add(ChoreAssignment(
                    chore_id=chore.id,
                    user_id=user.id,
                    due_date=target,
                ))
                created += 1

        db.session.commit()
        print(f"[scheduler] Generated {created} assignment(s) for {target}")
        return created


def send_due_reminders(app) -> int:
    """Email each user their incomplete assignments due today.
    Groups all chores for the same user into a single email.
    Returns the number of users emailed."""
    import os
    with app.app_context():
        today = date.today()
        app_url = os.environ.get('APP_URL', 'http://localhost:5000')

        pending = (
            ChoreAssignment.query
            .filter_by(due_date=today, reminder_sent=False)
            .filter(ChoreAssignment.completed_at.is_(None))
            .all()
        )

        # Group by user
        by_user: dict[int, list[ChoreAssignment]] = defaultdict(list)
        for a in pending:
            by_user[a.user_id].append(a)

        emailed = 0
        for user_id, assignments in by_user.items():
            user = User.query.get(user_id)
            if not user:
                continue
            chores_payload = [
                {'name': a.chore.name, 'description': a.chore.description}
                for a in assignments
            ]
            try:
                email_send_reminders(user.email, user.name, chores_payload, app_url)
                for a in assignments:
                    a.reminder_sent = True
                emailed += 1
            except Exception as exc:
                print(f"[scheduler] Failed to email {user.email}: {exc}")

        db.session.commit()
        print(f"[scheduler] Sent reminders to {emailed} user(s)")
        return emailed


def _daily_job(app):
    generate_assignments(app)
    send_due_reminders(app)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def init_scheduler(app) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone='UTC')
    scheduler.add_job(
        _daily_job,
        trigger='cron',
        hour=8,
        minute=0,
        args=[app],
        id='daily_chores',
        replace_existing=True,
    )
    scheduler.start()
    print("[scheduler] Started — daily job at 08:00 UTC")
    return scheduler
