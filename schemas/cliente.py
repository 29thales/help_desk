from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


def _so_digitos(valor: str) -> str:
    return "".join(c for c in (valor or "") if c.isdigit())


def _validar_cpf(cpf: str) -> bool:
    """Valida CPF (11 dígitos) com cálculo de dígito verificador."""
    cpf = _so_digitos(cpf)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    dig1 = (soma * 10) % 11
    if dig1 == 10:
        dig1 = 0
    if dig1 != int(cpf[9]):
        return False

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    dig2 = (soma * 10) % 11
    if dig2 == 10:
        dig2 = 0
    if dig2 != int(cpf[10]):
        return False

    return True


def _validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ (14 dígitos) com cálculo de dígito verificador."""
    cnpj = _so_digitos(cnpj)
    if len(cnpj) != 14:
        return False
    if cnpj == cnpj[0] * 14:
        return False

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    dig1 = soma % 11
    dig1 = 0 if dig1 < 2 else 11 - dig1
    if dig1 != int(cnpj[12]):
        return False

    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    dig2 = soma % 11
    dig2 = 0 if dig2 < 2 else 11 - dig2
    if dig2 != int(cnpj[13]):
        return False

    return True


def _validar_documento(valor):
    if not valor or not valor.strip():
        return None

    digitos = _so_digitos(valor)

    if len(digitos) == 11:
        if not _validar_cpf(digitos):
            raise ValueError("CPF inválido")
        return digitos

    if len(digitos) == 14:
        if not _validar_cnpj(digitos):
            raise ValueError("CNPJ inválido")
        return digitos

    raise ValueError(
        f"Documento deve ter 11 (CPF) ou 14 (CNPJ) dígitos. Informado: {len(digitos)} dígitos."
    )


class ClienteBase(BaseModel):
    nome: str
    email: EmailStr
    telefone: Optional[str] = None
    empresa: Optional[str] = None
    cnpj: Optional[str] = None
    endereco: Optional[str] = None
    responsavel: Optional[str] = None
    valor_hora: float = 130.00

    @field_validator("cnpj")
    @classmethod
    def validar_cnpj(cls, v):
        return _validar_documento(v)


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    telefone: Optional[str] = None
    empresa: Optional[str] = None
    cnpj: Optional[str] = None
    endereco: Optional[str] = None
    responsavel: Optional[str] = None
    valor_hora: Optional[float] = None
    ativo: Optional[bool] = None

    @field_validator("cnpj")
    @classmethod
    def validar_cnpj(cls, v):
        return _validar_documento(v)


class ClienteResposta(BaseModel):
    id: int
    nome: str
    email: str
    telefone: Optional[str] = None
    empresa: Optional[str] = None
    cnpj: Optional[str] = None
    endereco: Optional[str] = None
    responsavel: Optional[str] = None
    valor_hora: float = 130.00
    ativo: bool = True
    criado_em: Optional[datetime] = None

    class Config:
        orm_mode = True
        from_attributes = True
