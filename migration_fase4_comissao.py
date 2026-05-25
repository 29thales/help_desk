# ============================================
# MIGRATION FASE 4 - FECHAMENTO DE COMISSÃO
# ============================================
# Cria a tabela fechamento_comissao para registrar
# as comissões fechadas de cada técnico por mês.
# Idempotente + backup automático.
# ============================================

import sqlite3
import shutil
import os
import sys
from datetime import datetime

DB_PATH = "sistema_chamados.db"


def tabela_existe(cur, nome):
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (nome,),
    )
    return cur.fetchone() is not None


def fazer_backup():
    if not os.path.exists(DB_PATH):
        print(f"⚠️  Banco {DB_PATH} não encontrado.")
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bkp = f"{DB_PATH}.bkp_{timestamp}"
    shutil.copy2(DB_PATH, bkp)
    print(f"💾 Backup criado: {bkp}")
    return bkp


def migrar():
    print("=" * 60)
    print("MIGRATION FASE 4 - FECHAMENTO DE COMISSÃO")
    print("=" * 60)

    backup = fazer_backup()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        print("\n📋 Tabela `fechamento_comissao`:")
        if tabela_existe(cur, "fechamento_comissao"):
            print("  · fechamento_comissao já existe — pulando")
        else:
            cur.execute("""
                CREATE TABLE fechamento_comissao (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tecnico_id INTEGER NOT NULL REFERENCES usuarios(id),
                    ano INTEGER NOT NULL,
                    mes INTEGER NOT NULL,
                    percentual_aplicado FLOAT NOT NULL,
                    valor_base FLOAT NOT NULL,
                    valor_comissao FLOAT NOT NULL,
                    quantidade_chamados INTEGER NOT NULL DEFAULT 0,
                    observacoes TEXT,
                    fechado_em DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    fechado_por_id INTEGER REFERENCES usuarios(id),
                    UNIQUE(tecnico_id, ano, mes)
                )
            """)
            cur.execute(
                "CREATE INDEX ix_fechamento_periodo ON fechamento_comissao(ano, mes)"
            )
            print("  ✅ fechamento_comissao criada (com índice por período)")

        conn.commit()
        print("\n✅ MIGRATION CONCLUÍDA")
        if backup:
            print(f"💾 Backup em: {backup}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERRO: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    migrar()
