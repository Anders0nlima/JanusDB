# JanusDB — Notas de Implementação (M1 a M4)

Este documento compila as decisões arquiteturais, respostas teóricas e resumos de cada módulo implementado no JanusDB para a **Avaliação 1**.

---

## M1 — Resposta Obrigatória

**Página de 4096 bytes, cabeçalho de 16, registro de 8. O registro no slot 0 da página 2 começa em que byte?**

O registro no slot 0 da página 2 começa no byte **8208**.

A conta é feita da seguinte forma:
- **Início da página 2**: `2 * 4096 = 8192` (cada página ocupa 4096 bytes).
- **Fim do cabeçalho da página**: A página 2 começa em 8192, e possui 16 bytes de cabeçalho. Logo, o espaço de dados começa em `8192 + 16 = 8208`.
- **Deslocamento do Slot 0**: Por ser o primeiro slot, não pula nenhum registro anterior (`0 * 8 = 0`).
- **Total**: `8192 + 16 + 0 = 8208` (ocupando os bytes 8208 a 8215 no arquivo).

A função geral (`calcula_deslocamento(pagina, slot)`) implementada em `src/storage.py` centraliza essa regra:
$$\text{deslocamento}(\text{pagina}, \text{slot}) = (\text{pagina} \times \text{TAM\_PAGINA}) + \text{TAM\_CABECALHO} + (\text{slot} \times \text{TAM\_REGISTRO})$$

---

## Índice dos Módulos

As notas detalhadas de cada módulo, com suas implementações e principais dificuldades, encontram-se na pasta `notes/`:

1. [M1 — Página e arquivo de dados](notes/M1.md)
   - Leitura e escrita de blocos fixos de 4096 bytes em modo binário (`seek`, `read`, `write`).
   - Classe `Pager` com alocação, validações estritas (*fail fast*) e `sync()` via `os.fsync`.
   - Serialização binária em little-endian com `struct.pack` / `struct.unpack`.

2. [M2 — Cache de páginas](notes/M2.md)
   - Buffer pool em memória RAM com política de substituição LRU (*Least Recently Used*) sobre `OrderedDict`.
   - Rastreamento de páginas sujas (*dirty pages*) e persistência antes de evicção ou no `flush()`.
   - Mecanismo de fixação com `fixa` (*pin*) e `solta` (*unpin*) para proteger páginas em uso por iteradores.

3. [M3 — Árvore B+](notes/M3.md)
   - Índice em Árvore B+ persistente com nós de 4096 bytes operando sobre o `PageCache`.
   - Divisão de nós (*split*) de folhas com encadeamento horizontal (`proxima_pagina`) e divisão recursiva de nós internos.
   - Operações `search`, `insert`, `range_search` e `items`.

4. [M4 — Parser e catálogo](notes/M4.md)
   - Análise léxica (`tokenizer.py`) e parser por descida recursiva (`parser.py`) para `CREATE TABLE`, `INSERT` e `SELECT` com `WHERE`.
   - Catálogo de tabelas residente na **página 1** do arquivo com registros de 236 bytes.
   - Motor de execução (`engine.py`) e CLI com suporte a terminal interativo e entrada redirecionada (`minidb`).

5. [M5 — Executor: Varredura Sequencial e Operadores (Fase 0)](notes/M5_fase0.md)
   - Tabelas com múltiplas páginas encadeadas via ponteiro `proxima_pagina` no cabeçalho binário `<4sHHI4s`.
   - Mecanismo de fixação (*pin/unpin*) com proteção contra descarte LRU e rastreamento de `pin_count` no `PageCache`.
   - Modelo de iterador relacional (Volcano) com `SeqScan`, `Filter` e `Project` consumindo tuplas sob demanda.
   - Fechamento seguro de operadores com liberação irrestrita de alfinetes em bloco `try/finally`.

6. [M5 — Gramática Estendida, Codec de Linhas e Ordenação (Fase 1)](notes/M5_fase1.md)
   - Extensão do tokenizador e parser com `ORDER BY`, `GROUP BY`, `COUNT(*)` e `SUM(col)`.
   - Validação semântica de consultas agregadas e regras de ordenação no catálogo.
   - Codec binário universal (`CodecLinha`) para serialização de `INT`, `CHAR(n)` e `BIGINT`.
   - Operador `Sort` em memória com estabilidade e posicionamento antes do `Project`.

7. [M5 — Ordenação Externa, Agregação e Integração Completa (Fase 2)](notes/M5_fase2.md)
   - Ordenação externa com geração de runs ordenados e intercalação k-way via `MinHeap` estável.
   - Operador `Aggregate` por hash em memória para `COUNT(*)` e `SUM(col)` com suporte a acumuladores de 64 bits.
   - Intercalação com leitores de run fixando páginas no `PageCache` e streaming na última passada sem gravação.
   - Medição de I/O de disco via `ContadorPager` e exclusão segura de arquivos temporários no Windows.




