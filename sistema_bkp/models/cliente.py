# models/cliente.py

# 1. Importações Necessárias
from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base

# 2. Definição do Modelo Cliente
class Cliente(Base):
    """
    Representa um cliente no sistema Help Desk.
    Cada cliente pode ter múltiplos chamados associados e possui informações
    de contato e um valor/hora padrão para serviços.
    """
    
    __tablename__ = "clientes"

    # Colunas da tabela
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    telefone = Column(String(20), nullable=True)
    empresa = Column(String(255), nullable=True)
    valor_hora = Column(Float, default=130.00, nullable=False)
    
    criado_em = Column(DateTime, default=datetime.now, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # 3. Relacionamento
    # Um cliente pode ter vários chamados
    chamados = relationship("Chamado", back_populates="cliente")

    # 4. Método __repr__ para debug
    def __repr__(self):
        """Retorna uma representação string do objeto Cliente para depuração."""
        return (
            f"<Cliente(id={self.id}, nome='{self.nome}', email='{self.email}', "
            f"empresa='{self.empresa or 'N/A'}', valor_hora={self.valor_hora})>"
        )