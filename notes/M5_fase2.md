## M5 — Ordenação Externa, Agregação e Integração Completa (Fase 2)

Esta etapa conclui a implementação do **Tópico 6**, dotando o JanusDB de algoritmos clássicos para processamento de volumes de dados que excedem a capacidade da memória RAM através de **Ordenação Externa (External Merge Sort)**, bem como cálculo analítico de agregações por dispersão (**Hash Aggregate**) integrados ao modelo de iterador Volcano.

### 1. Ordenação Externa por Runs e Intercalação k-way (src/sort.py)
O operador relacional `Sort` suporta processamento em memória e em disco com parâmetro configurável de memória ($M$ páginas, $M \ge 3$):
* **Filtro de Memória:** caso o total de registros consumidos caiba em $M$ páginas, o operador ordena em memória via Timsort e **não gera arquivo temporário**.
* **Geração de Runs:** quando o volume excede a memória, o operador aloca um arquivo temporário gerenciado por um `ContadorPager` e um `PageCache` com capacidade $M - 1$. Os registros são lidos em lotes de tamanho $M \times \text{linhas\_por\_pagina}$, ordenados e persistidos em blocos de 4096 bytes como *runs* sequenciais.
* **Intercalação k-way com Min-Heap Manual:** para intercalar os runs, foi implementada uma estrutura `MinHeap` que mantém tuplas `ItemHeap(chave, id_run, linha, leitor)`. O campo `id_run` funciona como critério de desempate determinístico, garantindo que o algoritmo seja **estável**.
* **Ordenação Decrescente (`DESC`):** utiliza o invólucro `InverteComparacao` sobre as chaves, invertendo os operadores relacionais para que o mesmo min-heap produza ordenação decrescente sem duplicar estruturas.
* **Última Passada em Streaming:** quando restam no máximo $M - 1$ runs, a intercalação final não é persistida em disco: o método `proximo()` consome diretamente do min-heap e entrega as tuplas sob demanda para o operador superior.
* **Contagem de I/O:** a classe `ContadorPager` contabiliza leituras e escritas físicas, permitindo aferir experimentalmente o custo de I/O em comparação com o modelo teórico $2N(1 + \lceil \log_{M-1} \lceil N/M \rceil \rceil)$.

### 2. Agregação por Hash (src/aggregate.py)
O operador `Aggregate` implementa agrupamento em tempo linear $O(N)$ utilizando uma tabela hash em memória:
* **Acumuladores:** mapeia `chave_grupo → [acumuladores]`, suportando `COUNT(*)` (contagem de tuplas) e `SUM(col)` (acumulador de inteiros de precisão arbitrária, comportando valores superiores a 32 bits).
* **Decisões Semânticas:**
  * Ausência de `NULL`: somas sobre conjuntos vazios resultam em `0`;
  * Consultas com agregados sem `GROUP BY` sobre tabelas vazias retornam exatamente uma linha com `0`;
  * Consultas com `GROUP BY` sobre tabelas vazias retornam `(0 linhas)`.

### 3. Pipeline Integrado e Fechamento Seguro (src/engine.py)
O motor de execução unifica os operadores no fluxo relacional por demanda:
$$\text{SeqScan} \longrightarrow [\text{Filter}] \longrightarrow [\mathbf{Aggregate}] \longrightarrow [\mathbf{Sort}] \longrightarrow \text{Project}$$
* O `Filter` (`WHERE`) executa antes do `Aggregate`, garantindo filtragem prévia;
* O `Sort` executa antes do `Project` quando não há agrupamento (permitindo `ORDER BY` por colunas ocultas no resultado final), e após o `Aggregate` quando há agrupamento;
* O encerramento em blocos `try / finally` garante que todos os leitores soltem seus alfinetes (`solta`), o `PageCache` seja persistido, o `Pager` fechado e os arquivos temporários removidos do sistema de arquivos sem travamentos (`WinError 32` no Windows).

## Principais Dificuldades

A principal dificuldade neste módulo foi a orquestração do ciclo de vida dos leitores de run (`LeitorRun`) em conjunto com o `PageCache`: cada leitor em uma intercalação $k$-way fixa (*pin*) sua página física ativa para evitar que leitores concorrentes causem evicção mútua, exigindo sincronização estrita para soltar (*unpin*) a página esgotada antes de carregar a seguinte.

Outro desafio crítico foi o gerenciamento de arquivos temporários no ambiente Windows: qualquer tentativa de exclusão de arquivo com handles abertos dispara exceções de permissão. Isso exigiu encapsulamento rigoroso no método `fecha()` para assegurar que `PageCache.close()` e `Pager.fecha()` fossem executados antes da remoção física via `os.remove`.

Por fim, a integração sintática e semântica de consultas combinando simultaneamente projeções parciais, filtros de igualdade, agrupamentos e ordenações exigiu um mapeamento dinâmico de índices no operador `Project`, garantindo que as colunas retornassem na ordem exata definida no SQL independente da ordem interna dos agregadores.
