# JanusDB

SGBD construído do zero para a disciplina de Banco de Dados II.
Linguagem: Python.

## Módulos
- [X] M1 — Página e arquivo de dados
- [X] M2 — Cache de páginas
- [X] M3 — Árvore B+, busca e inserção
- [X] M4 — Parser e catálogo
- [X] M5 — Executor: varredura sequencial, ordenação externa e agregação (Tópico 6)
- [ ] M6 — Transações: BEGIN, COMMIT, ROLLBACK
- [ ] M7 — Recuperação: log de escrita antecipada

## Executável e CLI (M4 e M5)

O JanusDB disponibiliza o script executável `minidb` na raiz do projeto (ou `python -m src.cli`), suportando modo interativo e redirecionamento de entrada:

```bash
# Execução por lote (arquivo de consultas):
./minidb dados.db < consultas.sql

# Ou modo interativo:
./minidb dados.db
```

Comandos SQL suportados:
- `CREATE TABLE nome (coluna INT, coluna CHAR(n));`
- `INSERT INTO nome VALUES (1, 'Texto');`
- `SELECT * FROM nome;`
- `SELECT col1, col2 FROM nome WHERE col = valor;`
- `SELECT col1 FROM nome ORDER BY col2 [ASC | DESC];`
- `SELECT COUNT(*), SUM(col) FROM nome [WHERE col = valor];`
- `SELECT col, COUNT(*), SUM(col2) FROM nome [WHERE col = valor] GROUP BY col [ORDER BY col [ASC | DESC]];`

## Como rodar os testes

Para executar todos os testes do projeto (M1 ao M5):
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

# Testes do M5 / Tópico 6 (Ordenação Externa, Agregação e Consultas Combinadas)
$env:PYTHONPATH="."; pytest tests/test_sort.py tests/test_aggregate.py tests/test_combinadas.py -v
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
