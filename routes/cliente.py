# routes/cliente.py
#
# Endpoints específicos do cliente (Fase 3).
# Nunca expõe valores, nomes de técnicos, ou dados sensíveis.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field
from datetime import datetime

from database import get_db
from auth import obter_usuario_atual, get_password_hash, verify_password
from models.user import Usuario
from models.chamado import Chamado, HistoricoChamado
from models.cliente import Cliente

router = APIRouter()


# =========== HELPERS ===========

def _exigir_cliente(usuario: Usuario) -> Usuario:
    """403 se não for cliente ou não tiver cliente_id."""
    if getattr(usuario, "tipo_usuario", None) != "cliente":
        raise HTTPException(status_code=403, detail="Acesso restrito a clientes")
    if not usuario.cliente_id:
        raise HTTPException(
            status_code=403,
            detail="Seu usuário não está vinculado a uma empresa. Peça ao admin para ajustar.",
        )
    return usuario


# =========== TROCAR A PRÓPRIA SENHA ===========

class TrocarMinhaSenhaInput(BaseModel):
    senha_atual: str
    nova_senha: str = Field(..., min_length=6, max_length=100)


@router.post("/trocar-minha-senha")
async def trocar_minha_senha(
    dados: TrocarMinhaSenhaInput,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """
    Qualquer usuário autenticado pode trocar a própria senha.
    Usado principalmente pelo cliente no primeiro login
    (quando precisa_trocar_senha=true).
    """
    if not verify_password(dados.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    if dados.senha_atual == dados.nova_senha:
        raise HTTPException(status_code=400, detail="A nova senha precisa ser diferente da atual")

    usuario.senha_hash = get_password_hash(dados.nova_senha)
    usuario.precisa_trocar_senha = False
    db.commit()

    return {"mensagem": "Senha atualizada com sucesso"}


# =========== RESUMO PARA O DASHBOARD DO CLIENTE ===========

@router.get("/resumo")
async def resumo_cliente(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Estatísticas pessoais do cliente logado (escopo: chamados abertos POR ELE)."""
    _exigir_cliente(usuario)

    meus = db.query(Chamado).filter(Chamado.solicitante_id == usuario.id)

    # Aberto e atribuido contam como "aguardando"
    abertos = meus.filter(Chamado.status.in_(["aberto", "atribuido"])).count()
    em_atendimento = meus.filter(Chamado.status == "em_atendimento").count()

    # Finalizados este mês
    hoje = datetime.now()
    primeiro_do_mes = datetime(hoje.year, hoje.month, 1)
    finalizados_mes = meus.filter(
        Chamado.status == "finalizado",
        Chamado.data_termino >= primeiro_do_mes,
    ).count()

    total = meus.count()

    # Nome da empresa pra exibir no header
    emp = db.query(Cliente).filter(Cliente.id == usuario.cliente_id).first()
    nome_empresa = None
    if emp:
        nome_empresa = emp.empresa or emp.nome

    return {
        "nome_usuario": usuario.nome,
        "nome_empresa": nome_empresa,
        "abertos": abertos,
        "em_atendimento": em_atendimento,
        "finalizados_mes": finalizados_mes,
        "total": total,
    }


# =========== ABRIR CHAMADO PELO CLIENTE ===========

class AbrirChamadoClienteInput(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=255)
    descricao: str = Field(..., min_length=5)
    categoria: str = Field(default="geral", max_length=50)
    prioridade: str = Field(default="media", max_length=20)
    # Novo: cliente escolhe o tipo. Serviço específico fica para o técnico/admin.
    tipo_servico: str = Field(default="suporte_usuario", max_length=30)


@router.post("/chamado")
async def abrir_chamado_cliente(
    dados: AbrirChamadoClienteInput,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """
    Cliente abre chamado pra própria empresa.
    - cliente_id auto-preenchido do vínculo do usuário
    - solicitante_id = próprio cliente
    - status = aberto (vai pra fila)
    - tipo_servico = escolha do cliente (suporte_usuario ou suporte_tecnico)
    - Se for suporte_tecnico: servico_id fica null; técnico/admin define depois.
    - tecnico_id = null
    - valor = 0 (calculado pelo técnico/admin ao finalizar)
    """
    _exigir_cliente(usuario)

    if dados.prioridade not in ("baixa", "media", "alta", "urgente"):
        raise HTTPException(status_code=400, detail="Prioridade inválida")

    if dados.tipo_servico not in ("suporte_usuario", "suporte_tecnico"):
        raise HTTPException(status_code=400, detail="Tipo de serviço inválido")

    # Gera número
    ultimo = db.query(func.max(Chamado.id)).scalar() or 0
    numero = f"CHM-{ultimo + 1:04d}"

    novo = Chamado(
        numero=numero,
        titulo=dados.titulo.strip(),
        descricao=dados.descricao.strip(),
        categoria=dados.categoria.strip() or "geral",
        prioridade=dados.prioridade,
        cliente_id=usuario.cliente_id,
        solicitante_id=usuario.id,
        tipo_servico=dados.tipo_servico,
        status="aberto",
        tecnico_id=None,
        servico_id=None,          # Técnico/admin define depois
        servico_tecnico=None,
        valor_fixo=0.0,
        valor_total=0.0,
        data_inicio=datetime.now(),
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {
        "id": novo.id,
        "numero": novo.numero,
        "titulo": novo.titulo,
        "status": novo.status,
        "criado_em": novo.criado_em.isoformat() if novo.criado_em else None,
    }


# =========== LISTAR / VER OS PRÓPRIOS CHAMADOS ===========

def _serializar_para_cliente(chamado: Chamado, incluir_historico: bool = False) -> dict:
    """
    Versão ANONIMIZADA da serialização: nunca inclui
    valores, técnico, serviço interno, ou tempo/horário do histórico.
    """
    dados = {
        "id": chamado.id,
        "numero": chamado.numero,
        "titulo": chamado.titulo,
        "descricao": chamado.descricao,
        "categoria": chamado.categoria,
        "prioridade": chamado.prioridade,
        "status": chamado.status,
        "data_abertura": chamado.criado_em.isoformat() if chamado.criado_em else None,
        "data_termino": chamado.data_termino.isoformat() if chamado.data_termino else None,
    }

    if incluir_historico:
        # Histórico simplificado: só data + descrição.
        # Filtra mensagens automáticas de transferência/devolução (ruído interno
        # que confunde o cliente).
        historicos = []
        for h in sorted(chamado.historicos, key=lambda x: x.criado_em or datetime.min):
            desc = h.descricao or ""
            if desc.startswith(("🔄", "🔙")):
                # Evento operacional interno — cliente não precisa ver
                continue
            historicos.append({
                "data": (h.data_atendimento or h.criado_em).isoformat() if (h.data_atendimento or h.criado_em) else None,
                "descricao": desc,
            })
        dados["historico"] = historicos

    return dados


@router.get("/chamados")
async def listar_meus_chamados(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Lista chamados que ESTE cliente abriu (solicitante_id = usuario.id)."""
    _exigir_cliente(usuario)

    chamados = db.query(Chamado).filter(
        Chamado.solicitante_id == usuario.id,
    ).order_by(Chamado.criado_em.desc()).all()

    return [_serializar_para_cliente(c) for c in chamados]


@router.get("/chamados/{chamado_id}")
async def obter_meu_chamado(
    chamado_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Cliente só pode ver chamados que ele mesmo abriu."""
    _exigir_cliente(usuario)

    chamado = db.query(Chamado).filter(Chamado.id == chamado_id).first()
    if not chamado:
        raise HTTPException(status_code=404, detail="Chamado não encontrado")

    if chamado.solicitante_id != usuario.id:
        # Não revela se existe ou não — resposta uniforme
        raise HTTPException(status_code=403, detail="Você só pode ver chamados que abriu")

    return _serializar_para_cliente(chamado, incluir_historico=True)
