# Resposta M1

**Página de 4096 bytes, cabeçalho de 16, registro de 8. O registro no slot 0 da página 2 começa em que byte?**

O registro no slot 0 da página 2 começa no byte **8208**.

A conta é feita da seguinte forma:
- **Início da página 2**: `2 * 4096 = 8192` (cada página ocupa 4096 bytes).
- **Fim do cabeçalho**: A página 2 começa no 8192, e temos 16 bytes de cabeçalho na página. Então o espaço de dados da página começa em `8192 + 16 = 8208`.
- **Deslocamento do Slot 0**: Como é o slot 0, não precisamos pular nenhum registro anterior (`0 * 8 = 0`).
- **Total**: `8192 + 16 + 0 = 8208`.

A função geral (`calcula_deslocamento(pagina, slot)`) que implementamos no código resume essa fórmula:
`deslocamento(pagina, slot) = pagina * TAM_PAGINA + TAM_CABECALHO + slot * TAM_REGISTRO`

