from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ServicoCriar(BaseModel):
    nome: str = Field(..., min_length=2, max_length=150)
    categoria: str = Field(default="Manutenção", max_length=50)
    valor_padrao: float = Field(default=0.0, ge=0)
    ativo: bool = True


class ServicoAtualizar(BaseModel):
    nome: Optional[str] = Field(None, min_length=2, max_length=150)
    categoria: Optional[str] = Field(None, max_length=50)
    valor_padrao: Optional[float] = Field(None, ge=0)
    ativo: Optional[bool] = None


# Resposta "pública" (para combobox) - SEM VALOR
class ServicoPublico(BaseModel):
    id: int
    nome: str
    categoria: str

    class Config:
        from_attributes = True


# Resposta admin - COM valor e dados extras
class ServicoAdmin(BaseModel):
    id: int
    nome: str
    categoria: str
    valor_padrao: float
    ativo: bool
    criado_em: Optional[datetime] = None
    chamados_count: int = 0  # Quantos chamados usam esse serviço

    class Config:
        from_attributes = True
