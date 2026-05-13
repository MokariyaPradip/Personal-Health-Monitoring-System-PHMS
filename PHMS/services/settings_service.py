"""Service layer for user settings management.

Handles language and unit system preference updates.
"""

from config import db
from models import User
from schemas.settings_schema import validate_settings_payload


def get_user_settings(user: User) -> dict:
    """Get user's current language and unit system settings.
    
    Args:
        user: User object
    
    Returns:
        Dictionary with language and unit_system
    """
    return {
        'language': user.language or 'en',
        'unit_system': user.unit_system or 'metric'
    }


def update_user_settings(user: User, settings: dict) -> tuple[bool, dict]:
    """Update user's language and unit system settings.
    
    Args:
        user: User object to update
        settings: Dictionary with 'language' and/or 'unit_system' keys
    
    Returns:
        Tuple of (success, result) where:
        - success: True if update succeeded
        - result: Dictionary with:
            - 'success': True/False
            - 'updated': Dict of updated fields (if success)
            - 'errors': Dict mapping field names to error messages (if failure)
            - 'message': Human-readable message
    """
    # Validate settings
    model, errors = validate_settings_payload(settings)
    
    if errors:
        return False, {
            'success': False,
            'errors': errors,
            'message': 'Settings validation failed'
        }
    
    # Update only provided fields
    updated_fields = {}
    
    if model.language:
        user.language = model.language
        updated_fields['language'] = model.language
    
    if model.unit_system:
        user.unit_system = model.unit_system
        updated_fields['unit_system'] = model.unit_system
    
    try:
        db.session.commit()
        return True, {
            'success': True,
            'updated': updated_fields,
            'message': 'Settings updated successfully'
        }
    except Exception as e:
        db.session.rollback()
        return False, {
            'success': False,
            'errors': {'database': str(e)},
            'message': 'Failed to update settings'
        }
