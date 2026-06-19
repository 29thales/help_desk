"""
Migration: Múltiplos Serviços por Chamado
- Cria tabela chamado_servicos
- Migra chamados existentes de suporte_tecnico para a nova tabela
Idempotente: pode ser rodado mais de uma vez sem duplicar dados.
"""
import sys
import os
sys.path.insert(0, '/app')

from datetime import datetime
from sqlalchemy import text
from database import SessionLocal, engine

def criar_tabela(db):
    print("→ Verificando tabela chamado_servicos...")
    resultado = db.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='chamado_servicos'"
    )).fetchone()

    if resultado:
        print("  ✓ Tabela já existe, pulando criação.")
        return

    print("  → Criando tabela chamado_servicos...")
    db.execute(text("""
        CREATE TABLE chamado_servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chamado_id INTEGER NOT NULL REFERENCES chamados(id) ON DELETE CASCADE,
            servico_id INTEGER NOT NULL REFERENCES servicos_tecnicos(id),
            quantidade INTEGER NOT NULL DEFAULT 1,
            valor_unitario FLOAT NOT NULL DEFAULT 0.0,
            valor_total FLOAT NOT NULL DEFAULT 0.0,
            criado_em DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))
    db.execute(text("CREATE INDEX ix_chamado_servicos_chamado_id ON chamado_servicos(chamado_id)"))
    db.commit()
    print("  ✓ Tabela criada com sucesso.")

def migrar_dados(db):
    print("→ Migrando chamados existentes de suporte_tecnico...")

    chamados = db.execute(text("""
        SELECT id, servico_id, valor_fixo, valor_total, tempo_gasto_minutos
        FROM chamados
        WHERE tipo_servico = 'suporte_tecnico'
        AND servico_id IS NOT NULL
    """)).fetchall()

    print(f"  → Encontrados {len(chamados)} chamados técnicos com serviço vinculado.")

    migrados = 0
    pulados = 0

    for c in chamados:
        # Idempotente: verifica se já tem item migrado
        existente = db.execute(text(
            "SELECT id FROM chamado_servicos WHERE chamado_id = :cid"
        ), {"cid": c.id}).fetchone()

        if existente:
            pulados += 1
            continue

        quantidade = int(c.tempo_gasto_minutos or 1)
        if quantidade < 1:
            quantidade = 1

        valor_unit = float(c.valor_fixo or 0.0)
        valor_tot = float(c.valor_total or 0.0)

        # Se valor_total não bate com a conta, usa o que está gravado como valor_total
        db.execute(text("""
            INSERT INTO chamado_servicos
                (chamado_id, servico_id, quantidade, valor_unitario, valor_total, criado_em)
            VALUES
                (:chamado_id, :servico_id, :quantidade, :valor_unitario, :valor_total, :criado_em)
        """), {
            "chamado_id": c.id,
            "servico_id": c.servico_id,
            "quantidade": quantidade,
            "valor_unitario": valor_unit,
            "valor_total": valor_tot,
            "criado_em": datetime.now().isoformat(),
        })
        migrados += 1

    db.commit()
    print(f"  ✓ Migrados: {migrados} | Já existiam: {pulados}")

def validar(db):
    print("→ Validando resultado...")

    total_chamados_tecnicos = db.execute(text("""
        SELECT COUNT(*) FROM chamados
        WHERE tipo_servico = 'suporte_tecnico' AND servico_id IS NOT NULL
    """)).scalar()

    total_itens = db.execute(text(
        "SELECT COUNT(*) FROM chamado_servicos"
    )).scalar()

    print(f"  Chamados técnicos com serviço: {total_chamados_tecnicos}")
    print(f"  Itens em chamado_servicos:      {total_itens}")

    itens = db.execute(text("""
        SELECT cs.chamado_id, cs.servico_id, cs.quantidade, cs.valor_unitario, cs.valor_total
        FROM chamado_servicos cs
        ORDER BY cs.chamado_id
    """)).fetchall()

    if itens:
        print("\n  Itens migrados:")
        for i in itens:
            print(f"    Chamado #{i.chamado_id} | Serviço {i.servico_id} | "
                  f"Qtd {i.quantidade} | Unit R${i.valor_unitario:.2f} | Total R${i.valor_total:.2f}")
    else:
        print("  (nenhum item ainda — ok se não há chamados técnicos finalizados)")

if __name__ == "__main__":
    print("=" * 55)
    print("Migration: Múltiplos Serviços por Chamado")
    print("=" * 55)
    db = SessionLocal()
    try:
        criar_tabela(db)
        migrar_dados(db)
        validar(db)
        print("\n✅ Migration concluída com sucesso!")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro: {e}")
        raise
    finally:
        db.close()
