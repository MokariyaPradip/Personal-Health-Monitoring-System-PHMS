from pydantic import BaseModel, Field, ValidationError, validator
from typing import Optional, Dict, Any


class ProfileUpdateModel(BaseModel):
    username: Optional[str] = Field(None, min_length=2, max_length=50)
    gender: Optional[str] = Field(None)
    age: Optional[int] = Field(None)
    height: Optional[float] = Field(None)
    weight: Optional[float] = Field(None)

    @validator('age')
    def age_range(cls, v):
        if v is None:
            return v
        if v < 1 or v > 150:
            raise ValueError('Age must be between 1 and 150')
        return v

    @validator('height')
    def height_range(cls, v):
        if v is None:
            return v
        if v < 50 or v > 300:
            raise ValueError('Height must be between 50cm and 300cm')
        return v

    @validator('weight')
    def weight_range(cls, v):
        if v is None:
            return v
        if v < 10 or v > 500:
            raise ValueError('Weight must be between 10kg and 500kg')
        return v


def validate_profile_payload(payload: Dict[str, Any]):
    try:
        model = ProfileUpdateModel(**payload)
        return model, None
    except ValidationError as exc:
        errors = {}
        for err in exc.errors():
            loc = err.get('loc')
            msg = err.get('msg')
            if loc:
                errors[loc[0]] = msg
        return None, errors
