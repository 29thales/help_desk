# models/cliente.py

from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class Cliente(Base):
    """
    Representa um cliente no sistema Help Desk.
    """

    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    telefone = Column(String(20), nullable=True)
    empresa = Column(String(255), nullable=True)
    cnpj = Column(String(20), nullable=True)
    endereco = Column(String(500), nullable=True)
    responsavel = Column(String(255), nullable=True)
    valor_hora = Column(Float, default=130.00, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)

    criado_em = Column(DateTime, default=datetime.now, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relacionamento
    chamados = relationship("Chamado", back_populates="cliente")

    def __repr__(self):
        return (
            f"<Cliente(id={self.id}, nome='{self.nome}', email='{self.email}', "
            f"empresa='{self.empresa or 'N/A'}', valor_hora={self.valor_hora})>"
        )
