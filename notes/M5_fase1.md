## M5 — Gramática Estendida, Codec de Linhas e Ordenação (Fase 1)

Esta etapa expande as capacidades expressivas e analíticas do JanusDB, permitindo consultas ordenadas com `ORDER BY [ASC | DESC]`, introduzindo as regras sintáticas e semânticas para agregações (`COUNT`, `SUM`, `GROUP BY`), e implementando a infraestrutura de serialização binária com o operador relacional `Sort`.

### 1. Tokenizador e Parser (src/tokenizer.py e src/parser.py)
A gramática SQL do sistema foi estendida para suportar cláusulas de ordenação e agrupamento:
* **Palavras Reservadas:** foram adicionadas as palavras `ORDER`, `BY`, `GROUP`, `ASC` e `DESC`.
* **Tratamento de `COUNT` e `SUM`:** para não proibir que usuários criem colunas chamadas "count" ou "sum", essas funções não foram inseridas na lista de palavras reservadas. O parser as reconhece contextualmente como identificadores (`NOME`) seguidos imediatamente pelo símbolo `(`.
* **Árvore Sintática (AST):** os agregados são representados como tuplas estruturadas `("COUNT", "*")` e `("SUM", "coluna")`. Para manter compatibilidade absoluta com os testes legados da Avaliação 1, as chaves `"group_by"` e `"order_by"` só são inseridas no dicionário da AST quando as respectivas cláusulas forem explicitamente fornecidas na consulta.

### 2. Catálogo e Validação Semântica (src/catalog.py)
A análise semântica foi centralizada no método `valida_select()`, executado antes de qualquer acesso físico aos dados:
* Proíbe o uso do curinga `*` em consultas agregadas;
* Exige que qualquer coluna não agregada em uma consulta com agregação esteja estritamente declarada na cláusula `GROUP BY`;
* Assegura que `SUM` opere exclusivamente sobre colunas do tipo numérico `INT` e que `COUNT` receba apenas `*`;
* Valida que, em consultas agregadas, a cláusula `ORDER BY` ordene apenas pela coluna agrupada no `GROUP BY`.

### 3. Codec de Linhas Universal (src/sort.py)
Para permitir que linhas de tabelas sejam serializadas em blocos binários de tamanho fixo, foi criada a classe `CodecLinha`:
* **`INT`**: serializado em 4 bytes sem sinal little-endian (`<I`);
* **`CHAR(n)`**: codificado em UTF-8 e preenchido com zeros binários `\x00` até atingir exatamente `n` bytes;
* **`BIGINT`**: serializado em 8 bytes (`<q`), fornecendo suporte interno a acumuladores de soma sem risco de estouro de representação de 32 bits;
* O codec gerencia o cálculo exato de deslocamentos e o empacotamento defensivo (*fail-fast*), validando larguras de texto e cardinalidade de colunas.

### 4. Operador Sort e Pipeline no Engine (src/sort.py e src/engine.py)
O operador relacional `Sort` implementa a interface Volcano (`abre()`, `proximo()`, `fecha()`):
* Consome todas as tuplas do operador filho em `abre()`, ordena as linhas pela coluna indicada na ordem solicitada (`ASC` ou `DESC`) e garante a **estabilidade** da ordenação (linhas com chaves repetidas preservam sua ordem relativa de entrada);
* Rejeita valores de `mem_paginas < 3` com `ValueError`, preparando a infraestrutura para a futura intercalação externa;
* **Posicionamento no Pipeline:** no motor de execução, o `Sort` é encaixado **antes** do `Project`:
  $$\text{SeqScan} \longrightarrow [\text{Filter}] \longrightarrow [\mathbf{Sort}] \longrightarrow \text{Project}$$
  Essa decisão de projeto permite que consultas ordenem por colunas que não foram selecionadas na projeção final (como em `SELECT nome FROM aluno ORDER BY id`).

## Principais Dificuldades

A principal dificuldade nesta etapa foi garantir que a ampliação da gramática e da árvore sintática não gerasse efeitos colaterais nos testes existentes. A decisão de não tornar `COUNT` e `SUM` palavras reservadas exigiu um tratamento cuidadoso na descida recursiva do parser para diferenciar uma coluna de uma invocação funcional através do *lookahead* de parênteses.

Além disso, foi desafiador desacoplar o pipeline relacional no `engine.py` de modo que o `Sort` pudesse ordenar registros completos antes que o `Project` filtrasse as colunas solicitadas, garantindo que o ciclo de vida dos operadores continuasse estritamente protegido por blocos `try / finally` para evitar vazamentos de recursos e de alfinetes (*pins*) no `PageCache`.

Por fim, o projeto do `CodecLinha` demandou rigor no alinhamento binário e no tratamento de strings preenchidas com nulos para compatibilidade tanto com os esquemas declarados nas tabelas quanto com tipos virtuais internos (`BIGINT`), fundamentais para as próximas fases de intercalação em disco e agregação.
