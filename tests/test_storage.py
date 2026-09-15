import os
from src.storage import escreve_pagina, le_pagina, PAGE_SIZE

ARQUIVO_TESTE = "data/teste.db"

# preparando o ambiente
def setup_module():
    os.makedirs("data", exist_ok=True) 
    if os.path.exists(ARQUIVO_TESTE):
        os.remove(ARQUIVO_TESTE)

# quando eu peço uma pagina, recebo 4096 bytes? (teste1)
def test_pagina_tem_tamanho_certo():
    pagina = bytes(PAGE_SIZE)
    escreve_pagina(ARQUIVO_TESTE, 0, pagina)
    lida = le_pagina(ARQUIVO_TESTE, 0)
    assert len(lida) == PAGE_SIZE

# se eu escrever 4096 A, consigo recuperar os mesmos 4096 A? (teste2)
def test_escreve_e_le_a_mesma_pagina():
    conteudo = b"A" * PAGE_SIZE
    escreve_pagina(ARQUIVO_TESTE, 1, conteudo)
    assert le_pagina(ARQUIVO_TESTE, 1) == conteudo

# cada pagina realmente ocupa seu próprio espaço no arquivo? (teste3)
def test_paginas_diferentes_nao_se_misturam():
    pagina_a = b"A" * PAGE_SIZE
    pagina_b = b"B" * PAGE_SIZE
    escreve_pagina(ARQUIVO_TESTE, 2, pagina_a)
    escreve_pagina(ARQUIVO_TESTE, 3, pagina_b)
    assert le_pagina(ARQUIVO_TESTE, 2) == pagina_a
    assert le_pagina(ARQUIVO_TESTE, 3) == pagina_b