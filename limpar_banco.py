"""
Script de limpeza: remove colunas órfãs do banco que foram adicionadas
por migrações anteriores mas nunca foram usadas pelo sistema.

Colunas removidas:
- chamados.quantidade_total (adicionada por alterar_banco.py, nunca usada)
- historico_chamados.quantidade (adicionada por migracao_quantidade.py, nunca usada)

SQLite não suporta DROP COLUMN de forma simples em versões antigas, por isso
fazemos o processo manual: criar tabela nova sem a coluna, copiar dados,
apagar a antiga e renomear.

IMPORTANTE: faça BACKUP do arquivo sistema_chamados.db antes de rodar!
"""

import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = "sistema_chamados.db"


def fazer_backup():
    """Cria um backup do banco antes de qualquer alteração."""
    if not os.path.exists(DB_PATH):
        print(f"❌ Banco '{DB_PATH}' não encontrado.")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{DB_PATH}.backup_{timestamp}"
    shutil.copy2(DB_PATH, backup_path)
    print(f"✅ Backup criado: {backup_path}")
    return True


def coluna_existe(cursor, tabela, coluna):
    """Retorna True se a coluna existe na tabela."""
    cursor.execute(f"PRAGMA table_info({tabela});")
    colunas = [linha[1] for linha in cursor.fetchall()]
    return coluna in colunas


def remover_coluna_chamados_quantidade_total(cursor):
    """Remove coluna quantidade_total da tabela chamados."""
    if not coluna_existe(cursor, "chamados", "quantidade_total"):
        print("⚠️  Coluna 'quantidade_total' não existe em 'chamados'. Nada a fazer.")
        return

    print("🔧 Removendo coluna 'quantidade_total' de 'chamados'...")

    # Cria tabela nova sem a coluna (espelhando o model atual)
    cursor.execute("""
        CREATE TABLE chamados_nova (
            id INTEGER PRIMARY KEY,
            numero VARCHAR(20) UNIQUE NOT NULL,
            titulo VARCHAR(255) NOT NULL,
            descricao TEXT NOT NULL,
            categoria VARCHAR(50) NOT NULL DEFAULT 'geral',
            prioridade VARCHAR(20) NOT NULL DEFAULT 'media',
            status VARCHAR(20) NOT NULL DEFAULT 'aberto',
            tipo_servico VARCHAR(30) NOT NULL DEFAULT 'suporte_usuario',
            servico_tecnico VARCHAR(100),
            valor_fixo FLOAT NOT NULL DEFAULT 0.0,
            data_inicio DATETIME,
            data_termino DATETIME,
            tempo_gasto_minutos INTEGER NOT NULL DEFAULT 0,
            valor_total FLOAT NOT NULL DEFAULT 0.0,
            cliente_id INTEGER,
            solicitante_id INTEGER NOT NULL,
            criado_em DATETIME NOT NULL,
            atualizado_em DATETIME NOT NULL,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id),
            FOREIGN KEY (solicitante_id) REFERENCES usuarios(id)
        );
    """)

    # Copia os dados (ignora a coluna quantidade_total)
    cursor.execute("""
        INSERT INTO chamados_nova (
            id, numero, titulo, descricao, categoria, prioridade, status,
            tipo_servico, servico_tecnico, valor_fixo,
            data_inicio, data_termino, tempo_gasto_minutos, valor_total,
            cliente_id, solicitante_id, criado_em, atualizado_em
        )
        SELECT
            id, numero, titulo, descricao, categoria, prioridade, status,
            tipo_servico, servico_tecnico, valor_fixo,
            data_inicio, data_termino, tempo_gasto_minutos, valor_total,
            cliente_id, solicitante_id, criado_em, atualizado_em
        FROM chamados;
    """)

    # Remove a tabela antiga e renomeia a nova
    cursor.execute("DROP TABLE chamados;")
    cursor.execute("ALTER TABLE chamados_nova RENAME TO chamados;")

    # Recria o índice do campo numero (era único/index)
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_chamados_numero ON chamados(numero);")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_chamados_id ON chamados(id);")

    print("✅ Coluna 'quantidade_total' removida de 'chamados'.")


def remover_coluna_historico_quantidade(cursor):
    """Remove coluna quantidade da tabela historico_chamados."""
    if not coluna_existe(cursor, "historico_chamados", "quantidade"):
        print("⚠️  Coluna 'quantidade' não existe em 'historico_chamados'. Nada a fazer.")
        return

    print("🔧 Removendo coluna 'quantidade' de 'historico_chamados'...")

    cursor.execute("""
        CREATE TABLE historico_chamados_nova (
            id INTEGER PRIMARY KEY,
            chamado_id INTEGER NOT NULL,
            usuario_id INTEGER NOT NULL,
            descricao TEXT NOT NULL,
            tempo_minutos INTEGER NOT NULL DEFAULT 0,
            criado_em DATETIME NOT NULL,
            FOREIGN KEY (chamado_id) REFERENCES chamados(id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );
    """)

    cursor.execute("""
        INSERT INTO historico_chamados_nova (
            id, chamado_id, usuario_id, descricao, tempo_minutos, criado_em
        )
        SELECT
            id, chamado_id, usuario_id, descricao, tempo_minutos, criado_em
        FROM historico_chamados;
    """)

    cursor.execute("DROP TABLE historico_chamados;")
    cursor.execute("ALTER TABLE historico_chamados_nova RENAME TO historico_chamados;")

    cursor.execute("CREATE INDEX IF NOT EXISTS ix_historico_chamados_id ON historico_chamados(id);")

    print("✅ Coluna 'quantidade' removida de 'historico_chamados'.")


def mostrar_estrutura(cursor, tabela):
    """Mostra a estrutura final da tabela."""
    print(f"\n📋 Estrutura atual de '{tabela}':")
    cursor.execute(f"PRAGMA table_info({tabela});")
    for col in cursor.fetchall():
        cid, nome, tipo, notnull, default, pk = col
        pk_str = " [PK]" if pk else ""
        nn_str = " NOT NULL" if notnull else ""
        dft_str = f" DEFAULT {default}" if default is not None else ""
        print(f"   • {nome}: {tipo}{nn_str}{dft_str}{pk_str}")


def main():
    print("=" * 60)
    print("LIMPEZA DE COLUNAS ÓRFÃS DO BANCO")
    print("=" * 60)

    if not fazer_backup():
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Desativa foreign keys durante a operação (boas práticas para recriar tabelas)
        cursor.execute("PRAGMA foreign_keys = OFF;")

        remover_coluna_chamados_quantidade_total(cursor)
        remover_coluna_historico_quantidade(cursor)

        cursor.execute("PRAGMA foreign_keys = ON;")

        conn.commit()

        mostrar_estrutura(cursor, "chamados")
        mostrar_estrutura(cursor, "historico_chamados")

        conn.close()

        print("\n" + "=" * 60)
        print("✅ LIMPEZA CONCLUÍDA COM SUCESSO!")
        print("=" * 60)
        print("\nPróximos passos:")
        print("1. Reinicie o servidor (uvicorn)")
        print("2. Teste criar um chamado novo")
        print("3. Teste gerar o relatório de faturamento")
        print("\nSe algo der errado, restaure o backup gerado no início.")

    except Exception as e:
        print(f"\n❌ Erro durante a limpeza: {e}")
        print("Restaure o backup se necessário.")
        raise


if __name__ == "__main__":
    main()
