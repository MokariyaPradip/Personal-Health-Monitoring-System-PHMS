from pydantic import BaseModel, ConfigDict, ValidationError


class RequestSchema(BaseModel):
    """Base request schema config for inbound payload validation."""

    model_config = ConfigDict(
        extra='ignore',
        str_strip_whitespace=True,
    )


def validation_error_message(exc: ValidationError, fallback='Invalid input'):
    """Get a clean first validation message from a Pydantic ValidationError."""
    if not exc.errors():
        return fallback

    message = exc.errors()[0].get('msg', fallback)
    prefix = 'Value error, '
    if message.startswith(prefix):
        return message[len(prefix):]
    return message
