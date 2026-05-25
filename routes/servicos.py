from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from auth import obter_usuario_atual
from models.user import Usuario
from models.servico_tecnico import ServicoTecnico
from models.chamado import Chamado
from schemas.servico import (
    ServicoCriar, ServicoAtualizar,
    ServicoPublico, ServicoAdmin
)

router = APIRouter()


# =================== LISTAGEM ===================

@router.get("/")
async def listar_servicos(
    admin: bool = Query(False, description="Se true, retorna dados admin (com valor)"),
    incluir_inativos: bool = Query(False, description="Se true, inclui serviços inativos (rascunho)"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Lista serviços técnicos.

    - Modo normal (admin=false): só ativos, SEM valor (para combobox)
    - Modo admin (admin=true): todos os campos incluindo valor, contagem de chamados,
      e opcionalmente inativos (rascunho)
    """
    query = db.query(ServicoTecnico)

    if not admin or not incluir_inativos:
        # No modo combobox OU quando não pede explicitamente inativos
        if not incluir_inativos:
            query = query.filter(ServicoTecnico.ativo == True)

    servicos = query.order_by(ServicoTecnico.categoria, ServicoTecnico.nome).all()

    if admin:
        # Só admins podem ver dados com valores. Verifica flag do usuário.
        if not getattr(usuario, "is_admin", False):
            raise HTTPException(status_code=403, detail="Acesso restrito a administradores")

        # Conta chamados por serviço
        contagens = dict(
            db.query(Chamado.servico_id, func.count(Chamado.id))
              .filter(Chamado.servico_id.isnot(None))
              .group_by(Chamado.servico_id)
              .all()
        )

        return [
            {
                "id": s.id,
                "nome": s.nome,
                "categoria": s.categoria,
                "valor_padrao": s.valor_padrao,
                "ativo": s.ativo,
                "criado_em": s.criado_em.isoformat() if s.criado_em else None,
                "chamados_count": contagens.get(s.id, 0),
            }
            for s in servicos
        ]

    # Modo público: sem valor, só id/nome/categoria
    return [
        {"id": s.id, "nome": s.nome, "categoria": s.categoria}
        for s in servicos
    ]


# =================== CATEGORIAS ===================

@router.get("/categorias")
async def listar_categorias():
    """Lista de categorias disponíveis."""
    return [
        "Manutenção",
        "Hardware",
        "Software",
        "Rede",
        "Dados",
    ]


# =================== CRUD ===================

@router.post("/")
async def criar_servico(
    dados: ServicoCriar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    if not getattr(usuario, "is_admin", False):
        raise HTTPException(status_code=403, detail="Apenas administradores podem cadastrar serviços")

    # Evita nomes duplicados (case insensitive)
    existente = db.query(ServicoTecnico).filter(
        func.lower(ServicoTecnico.nome) == dados.nome.lower()
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail=f"Já existe um serviço com o nome '{dados.nome}'")

    servico = ServicoTecnico(
        nome=dados.nome.strip(),
        categoria=dados.categoria.strip() or "Manutenção",
        valor_padrao=float(dados.valor_padrao or 0),
        ativo=bool(dados.ativo),
    )
    db.add(servico)
    db.commit()
    db.refresh(servico)

    return {
        "id": servico.id,
        "nome": servico.nome,
        "categoria": servico.categoria,
        "valor_padrao": servico.valor_padrao,
        "ativo": servico.ativo,
    }


@router.get("/{servico_id}")
async def obter_servico(
    servico_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    servico = db.query(ServicoTecnico).filter(ServicoTecnico.id == servico_id).first()
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    # Se é admin, retorna com valor; se não, sem valor
    if getattr(usuario, "is_admin", False):
        return {
            "id": servico.id,
            "nome": servico.nome,
            "categoria": servico.categoria,
            "valor_padrao": servico.valor_padrao,
            "ativo": servico.ativo,
            "criado_em": servico.criado_em.isoformat() if servico.criado_em else None,
        }
    return {
        "id": servico.id,
        "nome": servico.nome,
        "categoria": servico.categoria,
    }


@router.put("/{servico_id}")
async def atualizar_servico(
    servico_id: int,
    dados: ServicoAtualizar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    if not getattr(usuario, "is_admin", False):
        raise HTTPException(status_code=403, detail="Apenas administradores podem editar serviços")

    servico = db.query(ServicoTecnico).filter(ServicoTecnico.id == servico_id).first()
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    dados_dict = dados.dict(exclude_unset=True) if hasattr(dados, 'dict') else dados.model_dump(exclude_unset=True)

    # Validação: nome único se for alterar
    if "nome" in dados_dict and dados_dict["nome"]:
        novo_nome = dados_dict["nome"].strip()
        existente = db.query(ServicoTecnico).filter(
            func.lower(ServicoTecnico.nome) == novo_nome.lower(),
            ServicoTecnico.id != servico_id
        ).first()
        if existente:
            raise HTTPException(status_code=400, detail=f"Já existe outro serviço com o nome '{novo_nome}'")
        dados_dict["nome"] = novo_nome

    for campo, valor in dados_dict.items():
        setattr(servico, campo, valor)

    db.commit()
    db.refresh(servico)

    return {
        "id": servico.id,
        "nome": servico.nome,
        "categoria": servico.categoria,
        "valor_padrao": servico.valor_padrao,
        "ativo": servico.ativo,
    }


@router.delete("/{servico_id}")
async def deletar_servico(
    servico_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual)
):
    if not getattr(usuario, "is_admin", False):
        raise HTTPException(status_code=403, detail="Apenas administradores podem remover serviços")

    servico = db.query(ServicoTecnico).filter(ServicoTecnico.id == servico_id).first()
    if not servico:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    # Verifica se tem chamados vinculados
    qtd_chamados = db.query(func.count(Chamado.id))\
        .filter(Chamado.servico_id == servico_id).scalar() or 0

    if qtd_chamados > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Não é possível remover: existe(m) {qtd_chamados} chamado(s) usando este serviço. Desative em vez de remover."
        )

    db.delete(servico)
    db.commit()
    return {"mensagem": "Serviço removido com sucesso"}
