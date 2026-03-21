from config import db
from datetime import datetime


class SmartwatchAccount(db.Model):
    """Linked smartwatch provider account for a user."""

    __tablename__ = 'smartwatch_account'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'provider', name='uq_smartwatch_account_user_provider'),
    )

    account_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.user_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    provider = db.Column(db.String(50), nullable=False, index=True)
    provider_user_id = db.Column(db.String(128), nullable=True)

    access_token = db.Column(db.Text, nullable=False)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expiry = db.Column(db.DateTime, nullable=True)
    scopes = db.Column(db.Text, nullable=True)

    connection_status = db.Column(db.String(20), nullable=False, default='connected')
    last_synced_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = db.relationship('User', back_populates='smartwatch_accounts')
    sync_state = db.relationship(
        'SmartwatchSyncState',
        back_populates='account',
        uselist=False,
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f"<SmartwatchAccount {self.account_id} user={self.user_id} provider={self.provider}>"
