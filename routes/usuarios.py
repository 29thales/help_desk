# routes/usuarios.py
#
# CRUD de usuários — TUDO restrito a admin.
# Cobre admins, técnicos e clientes.

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from database import get_db
from auth import obter_usuario_atual, get_password_hash
from models.user import Usuario
from models.cliente import Cliente
from schemas.usuario_schema import (
    UsuarioCriar,
    UsuarioAtualizar,
    UsuarioResposta,
    ResetarSenhaInput,
)

router = APIRouter()


# ====================================================
# HELPERS
# ====================================================

def _exigir_admin(usuario: Usuario):
    """Levanta 403 se não for admin."""
    if not (getattr(usuario, "tipo_usuario", None) == "admin" or getattr(usuario, "is_admin", False)):
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a administradores",
        )


def _serializar(u: Usuario, db: Session) -> dict:
    """Converte Usuario → dict pronto pra JSON, derivando nome_cliente_vinculado."""
    nome_cliente = None
    if u.cliente_id:
        cliente = db.query(Cliente).filter(Cliente.id == u.cliente_id).first()
        if cliente:
            nome_cliente = cliente.empresa or cliente.nome

    return {
        "id": u.id,
        "nome": u.nome or "",
        "email": u.email or "",
        "tipo_usuario": u.tipo_usuario or "tecnico",
        "is_admin": bool(u.is_admin),
        "ativo": bool(u.ativo) if u.ativo is not None else True,
        "comissao_percentual": float(u.comissao_percentual or 0),
        "pode_ver_fila_aberta": bool(u.pode_ver_fila_aberta),
        "cliente_id": u.cliente_id,
        "nome_cliente_vinculado": nome_cliente,
        "valor_hora": float(u.valor_hora or 0),
        "criado_em": u.criado_em.isoformat() if u.criado_em else None,
    }


def _validar_email_unico(db: Session, email: str, ignorar_id: int = None):
    q = db.query(Usuario).filter(func.lower(Usuario.email) == email.lower())
    if ignorar_id:
        q = q.filter(Usuario.id != ignorar_id)
    if q.first():
        raise HTTPException(status_code=400, detail=f"Já existe um usuário com o email '{email}'")


def _validar_cliente_existe(db: Session, cliente_id: int):
    if not db.query(Cliente).filter(Cliente.id == cliente_id).first():
        raise HTTPException(status_code=400, detail=f"Cliente id={cliente_id} não encontrado")


def _contar_admins_ativos(db: Session, ignorar_id: int = None) -> int:
    q = db.query(func.count(Usuario.id)).filter(
        Usuario.tipo_usuario == "admin",
        Usuario.ativo == True,
    )
    if ignorar_id:
        q = q.filter(Usuario.id != ignorar_id)
    return q.scalar() or 0


# ====================================================
# LISTAR
# ====================================================

@router.get("/")
async def listar_usuarios(
    tipo: str = Query(None, description="Filtra por tipo: admin/tecnico/cliente"),
    busca: str = Query(None, description="Busca por nome ou email"),
    incluir_inativos: bool = Query(True, description="Se false, esconde inativos"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    _exigir_admin(usuario)

    query = db.query(Usuario)

    if tipo and tipo in ("admin", "tecnico", "cliente"):
        query = query.filter(Usuario.tipo_usuario == tipo)

    if not incluir_inativos:
        query = query.filter(Usuario.ativo == True)

    if busca:
        termo = f"%{busca.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Usuario.nome).like(termo),
                func.lower(Usuario.email).like(termo),
            )
        )

    usuarios = query.order_by(Usuario.tipo_usuario, Usuario.nome).all()

    return [_serializar(u, db) for u in usuarios]


@router.get("/estatisticas")
async def estatisticas_usuarios(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    _exigir_admin(usuario)

    total = db.query(func.count(Usuario.id)).scalar() or 0
    admins = db.query(func.count(Usuario.id)).filter(Usuario.tipo_usuario == "admin").scalar() or 0
    tecnicos = db.query(func.count(Usuario.id)).filter(Usuario.tipo_usuario == "tecnico").scalar() or 0
    clientes = db.query(func.count(Usuario.id)).filter(Usuario.tipo_usuario == "cliente").scalar() or 0
    ativos = db.query(func.count(Usuario.id)).filter(Usuario.ativo == True).scalar() or 0

    return {
        "total": total,
        "admins": admins,
        "tecnicos": tecnicos,
        "clientes": clientes,
        "ativos": ativos,
        "inativos": total - ativos,
    }


@router.get("/tecnicos")
async def listar_tecnicos_ativos(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """
    Lista pública (qualquer autenticado) dos técnicos ATIVOS.
    Usada pelo select de transferência de chamado e pelo select de atribuição (admin).
    Retorna só id, nome, email e flag de elegibilidade — nunca dados sensíveis.
    """
    tecs = db.query(Usuario).filter(
        Usuario.tipo_usuario == "tecnico",
        Usuario.ativo == True,
    ).order_by(Usuario.nome).all()

    return [
        {
            "id": t.id,
            "nome": t.nome,
            "email": t.email,
            "pode_ver_fila_aberta": bool(t.pode_ver_fila_aberta),
        }
        for t in tecs
    ]


# ====================================================
# OBTER
# ====================================================

@router.get("/{usuario_id}")
async def obter_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    _exigir_admin(usuario)

    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    return _serializar(alvo, db)


# ====================================================
# CRIAR
# ====================================================

@router.post("/")
async def criar_usuario(
    dados: UsuarioCriar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    _exigir_admin(usuario)

    dados_validados = dados.model_dump_validado()

    _validar_email_unico(db, dados_validados["email"])

    # Cliente precisa de cliente_id
    if dados_validados["tipo_usuario"] == "cliente":
        if not dados_validados.get("cliente_id"):
            raise HTTPException(
                status_code=400,
                detail="Usuário do tipo 'cliente' precisa estar vinculado a uma empresa (cliente_id)",
            )
        _validar_cliente_existe(db, dados_validados["cliente_id"])

    novo = Usuario(
        nome=dados_validados["nome"].strip(),
        email=dados_validados["email"].strip().lower(),
        senha_hash=get_password_hash(dados_validados["senha"]),
        tipo_usuario=dados_validados["tipo_usuario"],
        is_admin=(dados_validados["tipo_usuario"] == "admin"),
        comissao_percentual=float(dados_validados.get("comissao_percentual") or 0),
        pode_ver_fila_aberta=bool(dados_validados.get("pode_ver_fila_aberta")),
        cliente_id=dados_validados.get("cliente_id"),
        ativo=True,
        valor_hora=0.0,
        # Cliente sempre precisa trocar a senha no primeiro login.
        # Admin/técnico já gerenciam a própria senha.
        precisa_trocar_senha=(dados_validados["tipo_usuario"] == "cliente"),
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return _serializar(novo, db)


# ====================================================
# ATUALIZAR
# ====================================================

@router.put("/{usuario_id}")
async def atualizar_usuario(
    usuario_id: int,
    dados: UsuarioAtualizar,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    _exigir_admin(usuario)

    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    dados_dict = dados.dict(exclude_unset=True) if hasattr(dados, "dict") else dados.model_dump(exclude_unset=True)

    # Email único
    if "email" in dados_dict and dados_dict["email"]:
        novo_email = dados_dict["email"].strip().lower()
        if novo_email != (alvo.email or "").lower():
            _validar_email_unico(db, novo_email, ignorar_id=usuario_id)
        dados_dict["email"] = novo_email

    # Validação cliente_id (só faz sentido se tipo=cliente)
    if "cliente_id" in dados_dict and dados_dict["cliente_id"] is not None:
        if alvo.tipo_usuario != "cliente":
            raise HTTPException(
                status_code=400,
                detail="Só usuários do tipo 'cliente' podem ter cliente_id vinculado",
            )
        _validar_cliente_existe(db, dados_dict["cliente_id"])

    # Comissão e pode_ver_fila_aberta só pra técnicos
    if alvo.tipo_usuario != "tecnico":
        dados_dict.pop("comissao_percentual", None)
        dados_dict.pop("pode_ver_fila_aberta", None)

    # Não deixa desativar admin único
    if dados_dict.get("ativo") is False and alvo.tipo_usuario == "admin":
        if _contar_admins_ativos(db, ignorar_id=usuario_id) == 0:
            raise HTTPException(
                status_code=400,
                detail="Não é possível desativar o último administrador ativo do sistema",
            )

    # Aplica
    for campo, valor in dados_dict.items():
        if hasattr(alvo, campo):
            setattr(alvo, campo, valor)

    db.commit()
    db.refresh(alvo)
    return _serializar(alvo, db)


# ====================================================
# RESETAR SENHA
# ====================================================

@router.post("/{usuario_id}/resetar-senha")
async def resetar_senha(
    usuario_id: int,
    dados: ResetarSenhaInput,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    _exigir_admin(usuario)

    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    alvo.senha_hash = get_password_hash(dados.nova_senha)
    # Se for cliente, força trocar a senha no próximo login
    if alvo.tipo_usuario == "cliente":
        alvo.precisa_trocar_senha = True
    db.commit()

    return {
        "mensagem": f"Senha de {alvo.email} redefinida com sucesso",
        "usuario_id": alvo.id,
    }


# ====================================================
# ATIVAR / DESATIVAR
# ====================================================

@router.post("/{usuario_id}/ativar")
async def ativar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    _exigir_admin(usuario)

    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    alvo.ativo = True
    db.commit()
    db.refresh(alvo)
    return _serializar(alvo, db)


@router.post("/{usuario_id}/desativar")
async def desativar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    _exigir_admin(usuario)

    alvo = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not alvo:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Não pode desativar último admin
    if alvo.tipo_usuario == "admin":
        if _contar_admins_ativos(db, ignorar_id=usuario_id) == 0:
            raise HTTPException(
                status_code=400,
                detail="Não é possível desativar o último administrador ativo do sistema",
            )

    alvo.ativo = False
    db.commit()
    db.refresh(alvo)
    return _serializar(alvo, db)
