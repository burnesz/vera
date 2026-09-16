from typing import Optional
from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """
    Formato da resposta após autenticação bem-sucedida.
    """
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """
    Estrutura decodificada do payload contido no JWT.
    """
    sub: Optional[str] = None
    role: Optional[str] = None
    exp: Optional[int] = None


class LoginRequest(BaseModel):
    """
    Schema para requisições de login via corpo JSON.
    """
    email: EmailStr
    password: str
