## M5 — Executor: Varredura Sequencial e Operadores (Fase 0)

O M5 estabelece a fundação do motor de execução de consultas do JanusDB, abandonando o modelo monolítico da Avaliação 1 (onde consultas carregavam páginas inteiras em listas na memória RAM) e adotando a arquitetura clássica de operadores por demanda (**Modelo Iterador / Volcano**), além de permitir que tabelas se expandam por múltiplas páginas no disco.

No armazenamento físico ([src/engine.py](file:///c:/Projetos/JanusDB/src/engine.py)), as páginas de dados das tabelas tiveram seu cabeçalho de 16 bytes reestruturado no formato `<4sHHI4s`: número mágico (`JDB4`), tamanho do registro (2 bytes), quantidade de slots ocupados (2 bytes), ponteiro de encadeamento `proxima_pagina` (4 bytes) e 4 bytes reservados. Com essa mudança, o método `_insere` navega até a última página da relação e, caso a capacidade máxima seja atingida (cerca de 145 a 170 linhas dependendo da largura do registro), aloca uma nova página via `Pager`, grava o registro no slot 0 e conecta a página anterior através de `proxima_pagina`, formando uma lista encadeada persistente no disco.

Na camada de memória ([src/cache.py](file:///c:/Projetos/JanusDB/src/cache.py)), foram integrados os métodos de fixação `fixa` (*pin*) e `solta` (*unpin*), além da propriedade `pin_count`. Durante a substituição LRU em `get_page()`, o cache ignora páginas com alfinetes ativos, impedindo que uma página em processamento seja descartada da memória RAM e levantando erro explícito caso o buffer pool se esgote com todas as páginas fixadas.

A camada de execução foi desacoplada no módulo [src/operadores.py](file:///c:/Projetos/JanusDB/src/operadores.py), introduzindo a classe abstrata `Operador` com os métodos `abre()`, `proximo()` e `fecha()`. Foram implementados:
- **`SeqScan`**: realiza a varredura sequencial física pelas páginas encadeadas da tabela, mantendo um alfinete (`fixa`) na página ativa e liberando-o (`solta`) antes de avançar para a página seguinte na cadeia;
- **`Filter`**: consome tuplas do operador filho e aplica a filtragem booleana referente à cláusula `WHERE`;
- **`Project`**: recebe as tuplas aprovadas e projeta apenas o subconjunto ordenado de colunas solicitadas na consulta.

O método `Engine.executa()` agora monta o pipeline relacional (`SeqScan` → `[Filter]` → `Project`) e consome os registros um a um, envolvendo toda a execução em um bloco `try / finally: pipeline.fecha()`, garantindo a liberação irrestrita de todos os alfinetes do cache mesmo diante de erros semânticos ou interrupções abruptas.

## Principais Dificuldades

A principal dificuldade neste módulo foi a transição arquitetural do modelo "em balde" (onde `_le_registros` lia toda a página diretamente para listas do Python) para o modelo de fluxo de tuplas sob demanda (Iterador Volcano). Foi desafiador controlar o estado interno do cursor no `SeqScan` (página atual, slot atual, contadores e limites) sem carregar todo o arquivo para a memória e garantindo o desembrulho binário correto dos tipos `INT` e `CHAR(n)`.

Além disso, exigiu cuidado extremo gerenciar a fixação de páginas (*pin/unpin*) em conjunto com a substituição LRU do `PageCache`: garantir que o alfinete proteja a página exatamente enquanto os slots locais estão sendo lidos, que a transição para a próxima página encadeada ocorra sem vazamento de alfinetes (*pin leaks*), e que o fechamento no bloco `finally` garanta `pin_count == 0` em qualquer cenário de falha.

Por fim, foi necessário conciliar a evolução do cabeçalho binário na página de dados reaproveitando o espaço previamente reservado no M1/M4, garantindo compatibilidade estrita com a geometria de 4096 bytes sem corromper a persistência do catálogo e preservando todos os testes automatizados legados.
