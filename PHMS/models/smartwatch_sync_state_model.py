from config import db
from datetime import datetime


class SmartwatchSyncState(db.Model):
    """Incremental sync cursor/timestamp and latest sync status for a provider."""

    __tablename__ = 'smartwatch_sync_state'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'provider', name='uq_smartwatch_sync_state_user_provider'),
    )

    state_id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(
        db.Integer,
        db.ForeignKey('smartwatch_account.account_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.user_id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    provider = db.Column(db.String(50), nullable=False, index=True)

    incremental_cursor = db.Column(db.String(255), nullable=True)
    incremental_since = db.Column(db.DateTime, nullable=True)

    last_synced_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    account = db.relationship('SmartwatchAccount', back_populates='sync_state')
    user = db.relationship('User', back_populates='smartwatch_sync_states')

    def __repr__(self):
        return f"<SmartwatchSyncState {self.state_id} user={self.user_id} provider={self.provider}>"
