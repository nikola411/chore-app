import os
import threading
from datetime import date, timedelta, datetime

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, flash, redirect, render_template, request, url_for

from models import Chore, ChoreAssignment, User, db
from scheduler import generate_assignments, send_due_reminders, init_scheduler

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def sync_members(app):
    raw = os.environ.get('MEMBERS', '').strip()
    if not raw:
        print('[members] MEMBERS env var not set — no members synced')
        return
    with app.app_context():
        for entry in raw.split(','):
            entry = entry.strip()
            if ':' not in entry:
                continue
            name, email = entry.split(':', 1)
            name, email = name.strip(), email.strip()
            user = User.query.filter_by(email=email).first()
            if user:
                user.name = name
            else:
                db.session.add(User(name=name, email=email))
        db.session.commit()
        print(f'[members] Synced {len(raw.split(","))} member(s) from MEMBERS env var')


def create_app() -> Flask:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'choreboard-secret')
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        os.environ.get('DATABASE_URL') or
        f'sqlite:///{os.path.join(BASE_DIR, "chores.db")}'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    # ------------------------------------------------------------------ dashboard
    @app.route('/')
    def dashboard():
        today = date.today()

        today_assignments = (
            ChoreAssignment.query
            .filter_by(due_date=today)
            .order_by(ChoreAssignment.chore_id)
            .all()
        )
        overdue = (
            ChoreAssignment.query
            .filter(
                ChoreAssignment.due_date < today,
                ChoreAssignment.completed_at.is_(None)
            )
            .order_by(ChoreAssignment.due_date)
            .all()
        )
        upcoming = (
            ChoreAssignment.query
            .filter(
                ChoreAssignment.due_date > today,
                ChoreAssignment.due_date <= today + timedelta(days=7)
            )
            .order_by(ChoreAssignment.due_date)
            .all()
        )

        stats = {
            'due_today': len(today_assignments),
            'completed_today': sum(1 for a in today_assignments if a.is_completed),
            'overdue': len(overdue),
        }

        return render_template(
            'dashboard.html',
            today=today,
            today_assignments=today_assignments,
            overdue=overdue,
            upcoming=upcoming,
            stats=stats,
        )

    # ------------------------------------------------------------------ assignments
    @app.route('/assignments/<int:assignment_id>/complete', methods=['POST'])
    def complete_assignment(assignment_id):
        assignment = ChoreAssignment.query.get_or_404(assignment_id)
        assignment.completed_at = datetime.utcnow()
        db.session.commit()
        flash(f'"{assignment.chore.name}" marked as done!', 'success')
        return redirect(request.referrer or url_for('dashboard'))

    @app.route('/assignments/<int:assignment_id>/uncomplete', methods=['POST'])
    def uncomplete_assignment(assignment_id):
        assignment = ChoreAssignment.query.get_or_404(assignment_id)
        assignment.completed_at = None
        db.session.commit()
        flash(f'"{assignment.chore.name}" marked as not done.', 'info')
        return redirect(request.referrer or url_for('dashboard'))

    # ------------------------------------------------------------------ chores
    @app.route('/chores')
    def chores_list():
        chores = Chore.query.order_by(Chore.name).all()
        return render_template('chores_list.html', chores=chores)

    @app.route('/chores/new', methods=['GET', 'POST'])
    def chore_new():
        users = User.query.order_by(User.name).all()
        if request.method == 'POST':
            return _save_chore(None, users)
        return render_template('chore_form.html', chore=None, users=users)

    @app.route('/chores/<int:chore_id>/edit', methods=['GET', 'POST'])
    def chore_edit(chore_id):
        chore = Chore.query.get_or_404(chore_id)
        users = User.query.order_by(User.name).all()
        if request.method == 'POST':
            return _save_chore(chore, users)
        return render_template('chore_form.html', chore=chore, users=users)

    @app.route('/chores/<int:chore_id>/delete', methods=['POST'])
    def chore_delete(chore_id):
        chore = Chore.query.get_or_404(chore_id)
        chore.active = False
        db.session.commit()
        flash(f'"{chore.name}" has been deactivated.', 'info')
        return redirect(url_for('chores_list'))

    def _save_chore(chore, users):
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        frequency_type = request.form.get('frequency_type', 'weekly')
        assignment_type = request.form.get('assignment_type', 'round_robin')
        assigned_user_id = request.form.get('assigned_user_id') or None

        if not name:
            flash('Chore name is required.', 'danger')
            return render_template('chore_form.html', chore=chore, users=users)

        frequency_value = None
        if frequency_type == 'weekly':
            selected_days = request.form.getlist('weekdays')
            if not selected_days:
                flash('Select at least one day for a weekly chore.', 'danger')
                return render_template('chore_form.html', chore=chore, users=users)
            frequency_value = ','.join(sorted(selected_days))
        elif frequency_type == 'custom':
            interval = request.form.get('custom_interval', '').strip()
            if not interval or not interval.isdigit() or int(interval) < 1:
                flash('Enter a valid interval (number of days >= 1).', 'danger')
                return render_template('chore_form.html', chore=chore, users=users)
            frequency_value = interval

        if assignment_type == 'specific' and not assigned_user_id:
            flash('Select a household member for specific assignment.', 'danger')
            return render_template('chore_form.html', chore=chore, users=users)

        if chore is None:
            chore = Chore()
            db.session.add(chore)

        chore.name = name
        chore.description = description or None
        chore.frequency_type = frequency_type
        chore.frequency_value = frequency_value
        chore.assignment_type = assignment_type
        chore.assigned_user_id = int(assigned_user_id) if assigned_user_id else None
        chore.active = True
        db.session.commit()

        flash(f'"{chore.name}" saved.', 'success')
        return redirect(url_for('chores_list'))

    # ------------------------------------------------------------------ admin actions
    @app.route('/admin/generate-assignments', methods=['POST'])
    def admin_generate():
        count = generate_assignments(app)
        flash(f'Generated {count} new assignment(s) for today.', 'success')
        return redirect(url_for('dashboard'))

    def _send_reminders_logged():
        try:
            count = send_due_reminders(app)
            print(f'[reminders] Done — sent to {count} member(s)')
        except Exception as e:
            print(f'[reminders] ERROR: {e}')

    @app.route('/admin/send-reminders', methods=['POST'])
    def admin_reminders():
        threading.Thread(target=_send_reminders_logged, daemon=True).start()
        flash('Reminders are being sent — check Render logs for result.', 'info')
        return redirect(url_for('dashboard'))

    return app


app = create_app()

with app.app_context():
    db.create_all()
    sync_members(app)

if os.environ.get('WERKZEUG_RUN_MAIN') != 'false':
    _scheduler = init_scheduler(app)

if __name__ == '__main__':
    app.run(debug=True)
