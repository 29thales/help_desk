from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models.cliente import Cliente
from schemas.cliente import ClienteCreate, ClienteUpdate, ClienteResposta
from auth import obter_usuario_atual

router = APIRouter(prefix="/clientes", tags=["Clientes"])

# LISTAR
@router.get("/", response_model=list[ClienteResposta])
async def listar_clientes(
    db: Session = Depends(get_db),
    usuario = Depends(obter_usuario_atual)
):
    return db.query(Cliente).all()

# CRIAR
@router.post("/", response_model=ClienteResposta)
async def criar_cliente(
    cliente: ClienteCreate,
    db: Session = Depends(get_db),
    usuario = Depends(obter_usuario_atual)
):
    cliente_existente = db.query(Cliente).filter(Cliente.email == cliente.email).first()

    if cliente_existente:
        raise HTTPException(status_code=400, detail="Cliente já existe")

    novo_cliente = Cliente(**cliente.dict())
    db.add(novo_cliente)
    db.commit()
    db.refresh(novo_cliente)

    return novo_cliente

# BUSCAR POR ID
@router.get("/{cliente_id}", response_model=ClienteResposta)
async def obter_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario = Depends(obter_usuario_atual)
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    return cliente

# ATUALIZAR
@router.put("/{cliente_id}", response_model=ClienteResposta)
async def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    db: Session = Depends(get_db),
    usuario = Depends(obter_usuario_atual)
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    for campo, valor in dados.dict(exclude_unset=True).items():
        setattr(cliente, campo, valor)

    db.commit()
    db.refresh(cliente)

    return cliente

# DELETAR
@router.delete("/{cliente_id}")
async def deletar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario = Depends(obter_usuario_atual)
):
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    db.delete(cliente)
    db.commit()

    return {"mensagem": "Cliente deletado com sucesso"}