# JanusDB

SGBD construído do zero para a disciplina de Banco de Dados II.
Linguagem: Python.

## Módulos
- [X] M1 — Página e arquivo de dados
- [X] M2 — Cache de páginas
- [X] M3 — Árvore B+, busca e inserção
- [ ] M4 — Parser e catálogo
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
