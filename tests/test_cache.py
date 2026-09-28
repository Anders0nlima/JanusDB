import os

from src.cache import PageCache
from src.storage import PAGE_SIZE, Pager


ARQUIVO_TESTE = "data/teste_cache.db"


def setup_function():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(ARQUIVO_TESTE):
        os.remove(ARQUIVO_TESTE)


def novo_pager_com_paginas(quantidade=3):
    pager = Pager(ARQUIVO_TESTE)
    paginas = []
    for _ in range(quantidade):
        paginas.append(pager.aloca())
    return pager, paginas


def test_primeiro_acesso_e_miss_e_segundo_e_hit():
    pager, paginas = novo_pager_com_paginas(1)
    cache = PageCache(pager, capacidade=2)

    cache.get_page(paginas[0])
    cache.get_page(paginas[0])

    assert cache.misses == 1
    assert cache.hits == 1
    assert len(cache) == 1
    assert cache.contains(paginas[0])

    cache.close()


def test_cache_reaproveita_mesma_pagina_em_memoria():
    pager, paginas = novo_pager_com_paginas(1)
    cache = PageCache(pager, capacidade=2)

    primeira = cache.get_page(paginas[0])
    primeira[0] = 123
    cache.mark_dirty(paginas[0])
    segunda = cache.get_page(paginas[0])

    assert primeira is segunda
    assert segunda[0] == 123

    cache.close()


def test_evict_lru_grava_pagina_suja():
    pager, paginas = novo_pager_com_paginas(3)
    cache = PageCache(pager, capacidade=2)

    p0 = cache.get_page(paginas[0])
    p0[0] = 42
    cache.mark_dirty(paginas[0])

    cache.get_page(paginas[1])
    # Torna a página 0 a mais recentemente usada.
    cache.get_page(paginas[0])
    # A página 1 passa a ser a LRU e deve ser removida.
    cache.get_page(paginas[2])

    assert cache.contains(paginas[0])
    assert not cache.contains(paginas[1])
    assert cache.contains(paginas[2])

    cache.flush()
    pager.fecha()

    pager2 = Pager(ARQUIVO_TESTE)
    assert pager2.le(paginas[0])[0] == 42
    pager2.fecha()


def test_pagina_suja_e_persistida_no_flush():
    pager, paginas = novo_pager_com_paginas(1)
    cache = PageCache(pager, capacidade=1)

    pagina = cache.get_page(paginas[0])
    pagina[:4] = b"M2!!"
    cache.mark_dirty(paginas[0])

    assert paginas[0] in cache.dirty_pages
    cache.flush()
    assert cache.dirty_pages == set()

    pager.fecha()

    pager2 = Pager(ARQUIVO_TESTE)
    assert pager2.le(paginas[0])[:4] == b"M2!!"
    pager2.fecha()


def test_write_page_valida_tamanho():
    pager, paginas = novo_pager_com_paginas(1)
    cache = PageCache(pager)

    try:
        cache.write_page(paginas[0], b"curto")
        assert False, "deveria rejeitar página com tamanho incorreto"
    except ValueError:
        pass
    finally:
        cache.close()


def test_capacidade_deve_ser_positiva():
    pager, _ = novo_pager_com_paginas(1)
    try:
        PageCache(pager, capacidade=0)
        assert False, "deveria rejeitar capacidade zero"
    except ValueError:
        pager.fecha()
