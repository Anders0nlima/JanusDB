# JanusDB

SGBD construído do zero para a disciplina de Banco de Dados II.
Linguagem: Python.

## Módulos
- [ ] M1 — Página e arquivo de dados
- [ ] M2 — Cache de páginas
- [ ] M3 — Árvore B+, busca e inserção
- [ ] M4 — Parser e catálogo
- [ ] M5 — Executor: varredura sequencial e por índice
- [ ] M6 — Transações: BEGIN, COMMIT, ROLLBACK
- [ ] M7 — Recuperação: log de escrita antecipada

## Como rodar os testes
    $env:PYTHONPATH="."; pytest tests/test_registro.py -v

## hexadecimal script
    python -c "
    with open('data/teste_registro.db', 'rb') as f:
        f.seek(8192)
        data = f.read(32)
        for i in range(0, len(data), 16):
           print(f'{8192+i:08x}  ' + ' '.join(f'{b:02x}' for b in data[i:i+16]))
"
