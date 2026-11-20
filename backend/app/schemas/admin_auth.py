from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=1024)

    def model_post_init(self, __context):
        self.email = self.email.strip().lower()


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

    admin_id: UUID
    name: str
    email: str
    role: str


class AdminIdentityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    email: str
    role: str
