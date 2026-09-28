import os
from src.storage import Pager, PAGE_SIZE

ARQUIVO_TESTE = "data/teste.db"

# preparando o ambiente
def setup_module():
    os.makedirs("data", exist_ok=True) 
    if os.path.exists(ARQUIVO_TESTE):
        os.remove(ARQUIVO_TESTE)

# quando eu peço uma pagina, recebo 4096 bytes? (teste1)
def test_pagina_tem_tamanho_certo():
    pager = Pager(ARQUIVO_TESTE)
    pagina = bytes(PAGE_SIZE)
    pager.escreve(0, pagina)
    lida = pager.le(0)
    assert len(lida) == PAGE_SIZE
    pager.fecha()

# se eu escrever 4096 A, consigo recuperar os mesmos 4096 A? (teste2)
def test_escreve_e_le_a_mesma_pagina():
    pager = Pager(ARQUIVO_TESTE)
    conteudo = b"A" * PAGE_SIZE
    pager.escreve(1, conteudo)
    assert pager.le(1) == conteudo
    pager.fecha()

# cada pagina realmente ocupa seu próprio espaço no arquivo? (teste3)
def test_paginas_diferentes_nao_se_misturam():
    pager = Pager(ARQUIVO_TESTE)
    pagina_a = b"A" * PAGE_SIZE
    pagina_b = b"B" * PAGE_SIZE
    pager.escreve(2, pagina_a)
    pager.escreve(3, pagina_b)
    assert pager.le(2) == pagina_a
    assert pager.le(3) == pagina_b
    pager.fecha()

# teste novo para o aloca()
def test_aloca_cria_pagina_em_branco():
    pager = Pager(ARQUIVO_TESTE)
    paginas_antes = pager.n_paginas
    
    nova_pagina_id = pager.aloca()
    
    assert nova_pagina_id == paginas_antes
    assert pager.n_paginas == paginas_antes + 1
    
    lida = pager.le(nova_pagina_id)
    assert lida == bytes(PAGE_SIZE) # deve ser toda de zeros
    pager.fecha()