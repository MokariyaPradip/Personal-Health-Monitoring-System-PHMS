from datetime import date, timedelta 
from flask_login import current_user 
from models import MedicationLog 
 
 
class MedicationLogReportingMixin: 
    """Read/reporting workflows for medication logs.""" 
    @staticmethod
    def get_medication_status(user_id=None):
        """
        Get medication adherence statistics for a user
        
        Args:
            user_id: ID of the user (defaults to current_user)
            
        Returns:
            dict: Adherence statistics
        """
        if user_id is None:
            user_id = current_user.user_id
        
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        logs = MedicationLog.query.filter(
            MedicationLog.user_id == user_id,
            MedicationLog.log_date >= week_ago
        ).all()
        
        taken = sum(1 for log in logs if log.status == 'taken')
        missed = sum(1 for log in logs if log.status == 'missed')
        pending = sum(1 for log in logs if log.status == 'pending')
        skipped = sum(1 for log in logs if log.status == 'skipped')
        total = len(logs)
        
        adherence_rate = (taken / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'taken': taken,
            'missed': missed,
            'pending': pending,
            'skipped': skipped,
            'adherence_rate': round(adherence_rate, 2),
            'period': f"Last 7 days (from {week_ago.strftime('%b %d')} to {today.strftime('%b %d')})"
        }


