from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class ClienteBase(BaseModel):
    nome: str
    email: EmailStr
    telefone: Optional[str] = None
    cnpj: Optional[str] = None
    endereco: Optional[str] = None
    responsavel: Optional[str] = None
    valor_hora: float = 130.00

class ClienteCreate(ClienteBase):
    pass

class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    cnpj: Optional[str] = None
    endereco: Optional[str] = None
    responsavel: Optional[str] = None
    valor_hora: Optional[float] = None
    ativo: Optional[bool] = None

class ClienteResposta(ClienteBase):
    id: int
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True