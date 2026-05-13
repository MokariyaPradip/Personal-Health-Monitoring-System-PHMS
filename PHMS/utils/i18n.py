"""Internationalization (i18n) utility for PHMS.

Provides translation dictionaries and locale helpers for multi-language support.
Supports English and Spanish with metric/imperial units.

Usage:
    >>> from PHMS.utils.i18n import get_translations
    >>> trans = get_translations('en')
    >>> print(trans['profile']['title'])
    'Profile'
"""

# Translation dictionaries for supported languages
TRANSLATIONS = {
    'en': {
        'profile': {
            'title': 'My Profile',
            'header_member_since': 'Member since',
            'header_days': 'days',
            'completion': 'Profile Completion',
            'completion_meta': 'Complete data improves health recommendations',
            'health_records': 'Health Records',
            'health_records_meta': 'Total entries tracked so far',
            'active_medications': 'Active Medications',
            'active_medications_critical': 'Critical',
            'unread_alerts': 'Unread Alerts',
            'unread_alerts_meta': 'Review recent notifications regularly',
            'latest_health_score': 'Latest Health Score',
            'latest_health_score_risk': 'Risk',
            'smartwatch_sync': 'Smartwatch Sync',
            'smartwatch_sync_on': 'On',
            'smartwatch_sync_off': 'Off',
            'personal_information': 'Personal Information',
            'username': 'Username',
            'email': 'Email',
            'member_since': 'Member Since',
            'gender': 'Gender',
            'age': 'Age',
            'age_unit': 'years',
            'health_metrics': 'Health Metrics',
            'height': 'Height',
            'weight': 'Weight',
            'bmi': 'BMI',
            'bmi_status': 'BMI Status',
            'smartwatch_integration': 'Smartwatch Integration',
            'last_successful_sync': 'Last successful sync',
            'never_synced': 'Never synced',
            'manual_records': 'Manual records',
            'smartwatch_records': 'Smartwatch records',
            'sync_errors': 'Sync errors',
            'health_snapshot': 'Health Snapshot',
            'latest_score': 'Latest score',
            'risk_level': 'Risk level',
            'tracked_records': 'Tracked records',
            'manual_vs_smartwatch': 'Manual vs smartwatch',
            'recommendations': 'Recommendations',
            'update_profile': '✏️ Update Profile',
            'change_password': '🔐 Change Password',
            'logout': '🚪 Logout',
            'update_modal_title': 'Update Profile Information',
            'change_password_modal_title': 'Change Password',
            'save': 'Save',
            'cancel': 'Cancel',
            'updating': 'Updating...',
            'updated_success': 'Profile updated successfully',
            'update_failed': 'Failed to update profile',
            'fill_all_fields': 'Please fill in all fields',
        },
        'units': {
            'height_short': 'cm',
            'height_full': 'centimeters',
            'weight_short': 'kg',
            'weight_full': 'kilograms',
            'bmi_short': 'kg/m²',
            'bmi_full': 'kg per square meter',
            'temperature': '°C',
            'pressure': 'mmHg',
        },
        'validation': {
            'age_invalid': 'Age must be between 1 and 150 years',
            'height_invalid': 'Height must be between 50 and 250 cm',
            'weight_invalid': 'Weight must be between 10 and 500 kg',
            'gender_invalid': 'Please select a valid gender',
            'username_invalid': 'Username must be 3-50 characters',
        }
    },
    'es': {
        'profile': {
            'title': 'Mi Perfil',
            'header_member_since': 'Miembro desde',
            'header_days': 'días',
            'completion': 'Perfil Completo',
            'completion_meta': 'Los datos completos mejoran las recomendaciones de salud',
            'health_records': 'Registros de Salud',
            'health_records_meta': 'Total de entradas rastreadas hasta ahora',
            'active_medications': 'Medicamentos Activos',
            'active_medications_critical': 'Crítico',
            'unread_alerts': 'Alertas No Leídas',
            'unread_alerts_meta': 'Revise las notificaciones recientes regularmente',
            'latest_health_score': 'Puntuación de Salud Más Reciente',
            'latest_health_score_risk': 'Riesgo',
            'smartwatch_sync': 'Sincronización de Reloj Inteligente',
            'smartwatch_sync_on': 'Activado',
            'smartwatch_sync_off': 'Desactivado',
            'personal_information': 'Información Personal',
            'username': 'Nombre de Usuario',
            'email': 'Correo Electrónico',
            'member_since': 'Miembro Desde',
            'gender': 'Género',
            'age': 'Edad',
            'age_unit': 'años',
            'health_metrics': 'Métricas de Salud',
            'height': 'Altura',
            'weight': 'Peso',
            'bmi': 'IMC',
            'bmi_status': 'Estado del IMC',
            'smartwatch_integration': 'Integración de Reloj Inteligente',
            'last_successful_sync': 'Última sincronización exitosa',
            'never_synced': 'Nunca sincronizado',
            'manual_records': 'Registros manuales',
            'smartwatch_records': 'Registros de reloj inteligente',
            'sync_errors': 'Errores de sincronización',
            'health_snapshot': 'Snapshot de Salud',
            'latest_score': 'Puntuación más reciente',
            'risk_level': 'Nivel de riesgo',
            'tracked_records': 'Registros rastreados',
            'manual_vs_smartwatch': 'Manual vs reloj inteligente',
            'recommendations': 'Recomendaciones',
            'update_profile': '✏️ Actualizar Perfil',
            'change_password': '🔐 Cambiar Contraseña',
            'logout': '🚪 Cerrar Sesión',
            'update_modal_title': 'Actualizar Información del Perfil',
            'change_password_modal_title': 'Cambiar Contraseña',
            'save': 'Guardar',
            'cancel': 'Cancelar',
            'updating': 'Actualizando...',
            'updated_success': 'Perfil actualizado correctamente',
            'update_failed': 'Error al actualizar el perfil',
            'fill_all_fields': 'Por favor, rellena todos los campos',
        },
        'units': {
            'height_short': 'cm',
            'height_full': 'centímetros',
            'weight_short': 'kg',
            'weight_full': 'kilogramos',
            'bmi_short': 'kg/m²',
            'bmi_full': 'kg por metro cuadrado',
            'temperature': '°C',
            'pressure': 'mmHg',
        },
        'validation': {
            'age_invalid': 'La edad debe estar entre 1 y 150 años',
            'height_invalid': 'La altura debe estar entre 50 y 250 cm',
            'weight_invalid': 'El peso debe estar entre 10 y 500 kg',
            'gender_invalid': 'Por favor, selecciona un género válido',
            'username_invalid': 'El nombre de usuario debe tener 3-50 caracteres',
        }
    }
}

def get_translations(language: str = 'en') -> dict:
    """Get translation dictionary for a specific language.
    
    Args:
        language: Language code ('en', 'es'). Defaults to 'en'.
    
    Returns:
        Dictionary containing translations for the language, or English as fallback.
    """
    return TRANSLATIONS.get(language, TRANSLATIONS['en'])

def get_supported_languages() -> list:
    """Get list of supported language codes."""
    return list(TRANSLATIONS.keys())
