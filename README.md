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

## Como rodar os testes

Para executar todos os testes (M1, M2 e M3):
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


## M4 — Parser, catálogo e SQL inicial

O M4 adiciona tokenizador (`src/tokenizer.py`), parser por descida recursiva
(`src/parser.py`), catálogo persistente (`src/catalog.py`) e execução SQL inicial
(`src/engine.py`). O REPL pode ser iniciado com:

```powershell
python -m src.cli data/meu_banco.db
```

Comandos suportados: `CREATE TABLE` com colunas `INT` e `CHAR(n)`, `INSERT INTO ... VALUES`
e `SELECT *` ou projeção de colunas, opcionalmente com `WHERE coluna = valor`.
Os metadados ficam em um arquivo lateral `<caminho-do-banco>.catalog.json`. Cada tabela
usa uma página de dados e, por isso, ao atingir a capacidade dessa página, o M4 informa
o limite; gerenciamento de múltiplas páginas e uso do índice serão evoluídos no M5.

Para testar o M4:

```powershell
python -m pytest tests/test_parser.py tests/test_catalog.py tests/test_engine.py -v
```
