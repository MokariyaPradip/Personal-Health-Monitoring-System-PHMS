"""Schema for user settings (language, unit system) updates."""

from pydantic import BaseModel, field_validator

class SettingsUpdateModel(BaseModel):
    """Validates user settings update request.
    
    Attributes:
        language: Preferred language code ('en', 'es', etc.)
        unit_system: Preferred unit system ('metric' or 'imperial')
    """
    language: str | None = None
    unit_system: str | None = None
    
    @field_validator('language')
    @classmethod
    def validate_language(cls, v):
        if v is None:
            return v
        # Supported languages
        supported = ['en', 'es']
        if v not in supported:
            raise ValueError(f"Language '{v}' is not supported. Choose from: {', '.join(supported)}")
        return v.lower()
    
    @field_validator('unit_system')
    @classmethod
    def validate_unit_system(cls, v):
        if v is None:
            return v
        if v not in ['metric', 'imperial']:
            raise ValueError("unit_system must be 'metric' or 'imperial'")
        return v.lower()


def validate_settings_payload(data: dict) -> tuple[SettingsUpdateModel | None, dict]:
    """Validate settings update payload using Pydantic.
    
    Args:
        data: Dictionary of settings to validate
    
    Returns:
        Tuple of (model, errors) where:
        - model: Valid SettingsUpdateModel if validation succeeds, else None
        - errors: Dict mapping field names to error messages (empty if valid)
    """
    try:
        model = SettingsUpdateModel(**data)
        return model, {}
    except ValueError as e:
        # Pydantic validation error
        return None, {'validation_error': str(e)}
    except Exception as e:
        # Catch-all for other errors
        return None, {'error': str(e)}
