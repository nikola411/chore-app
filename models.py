from flask_sqlalchemy import SQLAlchemy
from datetime import date

db = SQLAlchemy()

WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    assignments = db.relationship('ChoreAssignment', back_populates='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.name}>'


class Chore(db.Model):
    __tablename__ = 'chores'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    frequency_type = db.Column(db.String(20), nullable=False, default='weekly')
    frequency_value = db.Column(db.String(50))

    assignment_type = db.Column(db.String(20), nullable=False, default='round_robin')
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    last_assigned_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    assignments = db.relationship('ChoreAssignment', back_populates='chore', lazy='dynamic')
    assigned_user = db.relationship('User', foreign_keys=[assigned_user_id])
    last_assigned_user = db.relationship('User', foreign_keys=[last_assigned_user_id])

    @property
    def frequency_label(self):
        if self.frequency_type == 'daily':
            return 'Every day'
        elif self.frequency_type == 'weekly':
            if self.frequency_value:
                days = [WEEKDAY_NAMES[int(d)] for d in self.frequency_value.split(',') if d]
                return 'Weekly: ' + ', '.join(days)
            return 'Weekly'
        elif self.frequency_type == 'custom':
            return f'Every {self.frequency_value or "?"} days'
        return self.frequency_type

    def __repr__(self):
        return f'<Chore {self.name}>'


class ChoreAssignment(db.Model):
    __tablename__ = 'chore_assignments'

    id = db.Column(db.Integer, primary_key=True)
    chore_id = db.Column(db.Integer, db.ForeignKey('chores.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    reminder_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    chore = db.relationship('Chore', back_populates='assignments')
    user = db.relationship('User', back_populates='assignments')

    @property
    def is_completed(self):
        return self.completed_at is not None

    @property
    def is_overdue(self):
        return not self.is_completed and self.due_date < date.today()

    def __repr__(self):
        return f'<ChoreAssignment chore={self.chore_id} user={self.user_id} due={self.due_date}>'
