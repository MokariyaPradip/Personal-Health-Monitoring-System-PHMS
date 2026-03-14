from pydantic import field_validator

from .base import RequestSchema


class AddHealthRequest(RequestSchema):
    heart_rate: int | None = None
    temperature: float | None = None
    steps: int | None = None
    sleep_hours: float | None = None
    blood_pressure: float | None = None
    sugar: float | None = None

    @staticmethod
    def _optional_int(value, message):
        if value in (None, ''):
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(message) from exc

    @staticmethod
    def _optional_float(value, message):
        if value in (None, ''):
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(message) from exc

    @field_validator('heart_rate', mode='before')
    @classmethod
    def parse_heart_rate(cls, value):
        return cls._optional_int(value, 'Heart rate must be a valid number')

    @field_validator('steps', mode='before')
    @classmethod
    def parse_steps(cls, value):
        return cls._optional_int(value, 'Steps must be a valid number')

    @field_validator('temperature', mode='before')
    @classmethod
    def parse_temperature(cls, value):
        return cls._optional_float(value, 'Temperature must be a valid number')

    @field_validator('sleep_hours', mode='before')
    @classmethod
    def parse_sleep_hours(cls, value):
        return cls._optional_float(value, 'Sleep hours must be a valid number')

    @field_validator('blood_pressure', mode='before')
    @classmethod
    def parse_blood_pressure(cls, value):
        return cls._optional_float(value, 'Blood pressure must be a valid number')

    @field_validator('sugar', mode='before')
    @classmethod
    def parse_sugar(cls, value):
        return cls._optional_float(value, 'Blood sugar must be a valid number')

    @field_validator('heart_rate')
    @classmethod
    def validate_heart_rate(cls, value):
        if value is not None and (value < 30 or value > 220):
            raise ValueError('Heart rate must be between 30 and 220 bpm')
        return value

    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, value):
        if value is not None and (value < 35 or value > 42):
            raise ValueError('Temperature must be between 35°C and 42°C')
        return value

    @field_validator('steps')
    @classmethod
    def validate_steps(cls, value):
        if value is not None and (value < 0 or value > 60000):
            raise ValueError('Steps must be between 0 and 60,000')
        return value

    @field_validator('sleep_hours')
    @classmethod
    def validate_sleep_hours(cls, value):
        if value is not None and (value < 0 or value > 24):
            raise ValueError('Sleep hours must be between 0 and 24')
        return value

    @field_validator('blood_pressure')
    @classmethod
    def validate_blood_pressure(cls, value):
        if value is not None and (value < 40 or value > 250):
            raise ValueError('Blood pressure must be between 40 and 250 mmHg')
        return value

    @field_validator('sugar')
    @classmethod
    def validate_sugar(cls, value):
        if value is not None and (value < 40 or value > 600):
            raise ValueError('Blood sugar must be between 40 and 600 mg/dL')
        return value
