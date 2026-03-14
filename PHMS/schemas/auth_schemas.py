from pydantic import field_validator, model_validator

from .base import RequestSchema


def _normalize_email_value(value):
    if value is None:
        return ''
    return str(value).strip().lower()


def _is_simple_email_format(value):
    return '@' in value and '.' in value.split('@')[-1]


class RegisterRequest(RequestSchema):
    username: str | None = None
    email: str | None = None
    password: str | None = None
    age: int | None = None
    gender: str | None = None
    height: float | None = None
    weight: float | None = None

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return _normalize_email_value(value)

    @model_validator(mode='after')
    def validate_required(self):
        if not self.username or not self.email or not self.password:
            raise ValueError('Username, email, and password are required')
        return self

    @field_validator('username')
    @classmethod
    def validate_username(cls, value):
        if value is None:
            return value
        if len(value) < 2 or len(value) > 50:
            raise ValueError('Username must be between 2 and 50 characters')
        return value

    @field_validator('email')
    @classmethod
    def validate_email(cls, value):
        if value and not _is_simple_email_format(value):
            raise ValueError('Invalid email format')
        return value

    @field_validator('password')
    @classmethod
    def validate_password(cls, value):
        if value is not None and len(value) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return value


class LoginRequest(RequestSchema):
    email: str = ''
    password: str | None = None

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return _normalize_email_value(value)


class ForgotPasswordRequest(RequestSchema):
    email: str | None = None

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return _normalize_email_value(value)

    @model_validator(mode='after')
    def validate_required(self):
        if not self.email:
            raise ValueError('Email is required')
        return self


class ResetPasswordPayload(RequestSchema):
    email: str | None = None
    otp: str | None = None
    password: str | None = None
    confirm_password: str | None = None

    @field_validator('email', mode='before')
    @classmethod
    def normalize_email(cls, value):
        return _normalize_email_value(value)

    @field_validator('otp', mode='before')
    @classmethod
    def normalize_otp(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator('password', 'confirm_password', mode='before')
    @classmethod
    def normalize_password_fields(cls, value):
        if value is None:
            return None
        text = str(value)
        return text if text != '' else None

    @model_validator(mode='after')
    def validate_email_required(self):
        if not self.email:
            raise ValueError('Email is required')
        return self


class ResetPasswordVerifyOtpRequest(RequestSchema):
    email: str
    otp: str | None = None

    @model_validator(mode='after')
    def validate_required(self):
        if not self.otp:
            raise ValueError('No OTP found. Please request a new one.')
        return self


class ResetPasswordCompletionRequest(RequestSchema):
    email: str
    otp: str | None = None
    password: str | None = None
    confirm_password: str | None = None

    @model_validator(mode='after')
    def validate_required(self):
        if not self.otp:
            raise ValueError('OTP verification required. Please verify OTP first.')
        if not self.password or not self.confirm_password:
            raise ValueError('Invalid request. Missing required fields.')
        if self.password != self.confirm_password:
            raise ValueError('Passwords do not match')
        if len(self.password) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return self


class ChangePasswordRequest(RequestSchema):
    current_password: str | None = None
    new_password: str | None = None
    confirm_password: str | None = None

    @model_validator(mode='after')
    def validate_required(self):
        if not self.current_password or not self.new_password or not self.confirm_password:
            raise ValueError('All fields are required')
        if self.new_password != self.confirm_password:
            raise ValueError('Passwords do not match')
        if len(self.new_password) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return self
