# JanusDB

SGBD construído do zero para a disciplina de Banco de Dados II.
Linguagem: Python.

## Módulos
- [X] M1 — Página e arquivo de dados
- [X] M2 — Cache de páginas
- [X] M3 — Árvore B+, busca e inserção
- [X] M4 — Parser e catálogo
- [ ] M5 — Executor: varredura sequencial e por índice
- [ ] M6 — Transações: BEGIN, COMMIT, ROLLBACK
- [ ] M7 — Recuperação: log de escrita antecipada

## Como executar o CLI (M4)

O JanusDB disponibiliza um REPL interativo via terminal para execução direta de instruções SQL:

```powershell
python -m src.cli data/banco.db
```

Comandos SQL suportados:
- `CREATE TABLE nome (coluna INT, coluna CHAR(n));`
- `INSERT INTO nome VALUES (1, 'Texto');`
- `SELECT * FROM nome;`
- `SELECT col1, col2 FROM nome WHERE col = valor;`

## Como rodar os testes

Para executar todos os testes do projeto (M1 ao M4):
```powershell
$env:PYTHONPATH="."; pytest tests -v
```

Para executar testes específicos de cada módulo:
```powershell
# Testes do M1 (Página e Arquivo de Dados)
$env:PYTHONPATH="."; pytest tests/test_storage.py tests/test_registro.py -v

# Testes do M2 (Cache de Páginas)
$env:PYTHONPATH="."; pytest tests/test_cache.py -v

# Testes do M3 (Árvore B+)
$env:PYTHONPATH="."; pytest tests/test_btree.py -v

# Testes do M4 (Parser, Catálogo e Engine)
$env:PYTHONPATH="."; pytest tests/test_parser.py tests/test_catalog.py tests/test_engine.py -v
```

## Verificação Hexadecimal do Registro (M1)

```powershell
python -c "
with open('data/teste_registro.db', 'rb') as f:
    f.seek(8192)
    data = f.read(32)
    for i in range(0, len(data), 16):
        print(f'{8192+i:08x}  ' + ' '.join(f'{b:02x}' for b in data[i:i+16]))
"
```
