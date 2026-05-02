from datetime import date, datetime

from pydantic import field_validator, model_validator

from .base import RequestSchema
from utils.medication_schedule import SUPPORTED_MEDICATION_FREQUENCIES


class AddMedicationRequest(RequestSchema):
    medicine_name: str | None = None
    dosage: str | None = None
    frequency: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_critical: bool = False

    @model_validator(mode='after')
    def validate_required(self):
        if not self.medicine_name or not self.dosage or self.frequency is None or self.start_date is None or self.end_date is None:
            raise ValueError('All fields are required')
        return self

    @field_validator('frequency', mode='before')
    @classmethod
    def parse_frequency(cls, value):
        if value in (None, ''):
            return None
        try:
            frequency = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError('Frequency must be a valid number (1=once, 2=twice, 3=thrice, 4=four times, 6=six times daily)') from exc

        if frequency not in SUPPORTED_MEDICATION_FREQUENCIES:
            allowed = ', '.join(str(item) for item in SUPPORTED_MEDICATION_FREQUENCIES)
            raise ValueError(f'Unsupported frequency. Choose one of: {allowed}')

        return frequency

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def parse_iso_date(cls, value):
        if value in (None, ''):
            return None
        if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
            return value
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid date format. Use YYYY-MM-DD.') from exc

    @field_validator('is_critical', mode='before')
    @classmethod
    def parse_bool(cls, value):
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return False


class UpdateMedicationRequest(RequestSchema):
    medicine_name: str | None = None
    dosage: str | None = None
    frequency: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_critical: bool = False

    @model_validator(mode='after')
    def validate_required(self):
        if not self.medicine_name or not self.dosage or self.frequency is None or self.start_date is None or self.end_date is None:
            raise ValueError('All fields are required')
        return self

    @field_validator('frequency', mode='before')
    @classmethod
    def parse_frequency(cls, value):
        if value in (None, ''):
            return None
        try:
            frequency = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError('Frequency must be a valid number (1=once, 2=twice, 3=thrice, 4=four times, 6=six times daily)') from exc

        if frequency not in SUPPORTED_MEDICATION_FREQUENCIES:
            allowed = ', '.join(str(item) for item in SUPPORTED_MEDICATION_FREQUENCIES)
            raise ValueError(f'Unsupported frequency. Choose one of: {allowed}')

        return frequency

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def parse_iso_date(cls, value):
        if value in (None, ''):
            return None
        if hasattr(value, 'year') and hasattr(value, 'month') and hasattr(value, 'day'):
            return value
        try:
            return datetime.strptime(str(value), '%Y-%m-%d').date()
        except (TypeError, ValueError) as exc:
            raise ValueError('Invalid date format. Use YYYY-MM-DD.') from exc

    @field_validator('is_critical', mode='before')
    @classmethod
    def parse_bool(cls, value):
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {'1', 'true', 'yes', 'on'}
        return False


class AddMedicineMasterRequest(RequestSchema):
    medicine_name: str | None = None
    medicine_type: str | None = None
    purpose: str | None = None
    remark: str | None = None

    @field_validator('medicine_type', 'remark', mode='before')
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @model_validator(mode='after')
    def validate_required(self):
        if not self.medicine_name or not self.purpose:
            raise ValueError('Required fields missing')
        return self
