# models/servico_tecnico.py

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime

from database import Base


class ServicoTecnico(Base):
    """
    Catálogo de serviços técnicos disponíveis.
    Cada serviço tem um nome, categoria e valor padrão sugerido.
    O valor é usado apenas como sugestão quando o admin finaliza o chamado.
    """
    __tablename__ = "servicos_tecnicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(150), nullable=False)
    categoria = Column(String(50), default="Manutenção", nullable=False)
    valor_padrao = Column(Float, default=0.0, nullable=False)
    # Se ativo=False, o serviço é rascunho e não aparece no combobox de abertura
    ativo = Column(Boolean, default=True, nullable=False, index=True)
    criado_em = Column(DateTime, default=datetime.now, nullable=False)

    def __repr__(self):
        return f"<ServicoTecnico(id={self.id}, nome='{self.nome}', ativo={self.ativo})>"
