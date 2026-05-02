from .base import RequestSchema, validation_error_message
from .auth_schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordCompletionRequest,
    ResetPasswordPayload,
    ResetPasswordVerifyOtpRequest,
)
from .health_schemas import AddHealthRequest
from .medication_schemas import AddMedicationRequest, AddMedicineMasterRequest, UpdateMedicationRequest

__all__ = [
    'RequestSchema',
    'validation_error_message',
    'RegisterRequest',
    'LoginRequest',
    'ForgotPasswordRequest',
    'ResetPasswordPayload',
    'ResetPasswordVerifyOtpRequest',
    'ResetPasswordCompletionRequest',
    'ChangePasswordRequest',
    'AddHealthRequest',
    'AddMedicationRequest',
    'AddMedicineMasterRequest',
    'UpdateMedicationRequest',
]
