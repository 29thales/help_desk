# FASE 1 — Base Multi-Usuário

Entrega da Fase 1 do briefing: estrutura de banco + tela de gerenciamento
de usuários. **Não altera** fluxo de chamados/faturamento/serviços.

---

## Como aplicar no projeto existente

O ZIP mantém a mesma estrutura de pastas do projeto. Basta copiar os
arquivos por cima. Ordem recomendada:

### 1. Backup manual (segurança extra)

Mesmo que a migration faça backup automático, recomendo copiar o
`sistema_chamados.db` para um lugar seguro antes de começar.

### 2. Copie os arquivos

Descompacte o ZIP e copie para a raiz do projeto respeitando a estrutura:

```
sistema_chamados_22_04_2026/
├── migration_multi_usuario.py     (NOVO - raiz)
├── main.py                        (ATUALIZADO)
├── auth.py                        (ATUALIZADO - só o /me)
├── models/
│   ├── user.py                    (ATUALIZADO)
│   └── chamado.py                 (ATUALIZADO)
├── schemas/
│   ├── usuario_schema.py          (NOVO)
│   └── user.py                    (ATUALIZADO - virou shim)
├── routes/
│   └── usuarios.py                (NOVO)
└── templates/
    ├── usuarios.html              (NOVO)
    ├── dashboard.html             (ATUALIZADO - header)
    ├── clientes.html              (ATUALIZADO - header)
    ├── chamados.html              (ATUALIZADO - header)
    ├── faturamento.html           (ATUALIZADO - header)
    └── servicos.html              (ATUALIZADO - header)
```

### 3. Rode a migration

```bash
cd sistema_chamados_22_04_2026
python migration_multi_usuario.py
```

A migration é **idempotente** — pode rodar quantas vezes quiser, só
aplica o que ainda não foi aplicado. Ela já cria um backup do banco
no formato `sistema_chamados.db.bkp_<timestamp>` antes de começar.

### 4. Reinicie o servidor

```bash
python main.py
```

Se algo der errado, restaure o backup:
```bash
cp sistema_chamados.db.bkp_<timestamp> sistema_chamados.db
```

---

## O que foi feito

### Banco
- `usuarios`: +`tipo_usuario`, +`cliente_id`, +`comissao_percentual`,
  +`pode_ver_fila_aberta`, +`ativo`
- `chamados`: +`tecnico_id`, +`motivo_devolucao`
- Nova tabela `chamado_transferencias` (auditoria)
- Admin existente marcado como `tipo_usuario='admin'`

### Backend
- Rota `/api/usuarios/` com CRUD completo (só admin):
  - `GET /` — listar (filtros: tipo, busca, incluir_inativos)
  - `GET /estatisticas` — contagens
  - `GET /{id}` — obter
  - `POST /` — criar
  - `PUT /{id}` — atualizar
  - `POST /{id}/resetar-senha` — admin define a nova senha
  - `POST /{id}/ativar` e `/desativar`
- Validações: email único, cliente precisa ter cliente_id, comissão
  0-100, não permite desativar último admin ativo
- `/api/usuario-logado` agora retorna `tipo_usuario`

### Frontend
- Nova página `/usuarios/pagina` — design idêntico ao `/servicos/pagina`
- Header: link "👫 Usuários" em todas as páginas, visível apenas pra
  admin (escondido via JS)

---

## O que NÃO foi feito (Fases futuras)

- ❌ Área do técnico (Fase 2)
- ❌ Área do cliente (Fase 3)
- ❌ Ciclo atribuir/puxar/transferir/devolver (Fase 2)
- ❌ Relatório de comissão mensal (Fase 4)

---

## Credenciais

Admin padrão continua o mesmo: `admin@helpdesk.com` / `admin123456`
