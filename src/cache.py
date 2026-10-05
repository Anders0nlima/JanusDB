from collections import OrderedDict

from .storage import PAGE_SIZE, Pager


class PageCache:
    def __init__(self, pager: Pager, capacidade: int = 8):
        if capacidade <= 0:
            raise ValueError("A capacidade do cache deve ser maior que zero")

        self.pager = pager
        self.capacidade = capacidade
        # page_id -> bytearray. A ordem representa do menos para o mais usado.
        self._paginas: OrderedDict[int, bytearray] = OrderedDict()
        self._dirty: set[int] = set()
        self.hits = 0
        self.misses = 0

    def _valida_pagina(self, pagina: int) -> None:
        if not isinstance(pagina, int) or isinstance(pagina, bool) or pagina < 0:
            raise ValueError(f"Página inválida: {pagina}")

    def get_page(self, pagina: int) -> bytearray:
        #Retorna uma página do cache, carregando-a do Pager se necessário.
        self._valida_pagina(pagina)

        if pagina in self._paginas:
            self.hits += 1
            self._paginas.move_to_end(pagina)
            return self._paginas[pagina]

        self.misses += 1

        # Se o cache estiver cheio, remove a página LRU. Uma página suja
        # precisa ser persistida antes de perdermos sua única cópia em RAM.
        if len(self._paginas) >= self.capacidade:
            vitima = next(iter(self._paginas))
            self._flush_page(vitima)
            del self._paginas[vitima]

        dados = self.pager.le(pagina)
        self._paginas[pagina] = dados
        return dados

    def mark_dirty(self, pagina: int) -> None:
        #Marca uma página em cache como modificada.
        self._valida_pagina(pagina)
        if pagina not in self._paginas:
            raise KeyError(f"Página {pagina} não está no cache")
        self._dirty.add(pagina)

    def write_page(self, pagina: int, dados: bytes | bytearray) -> None:
        #Substitui o conteúdo de uma página do cache e a marca como suja.
        self._valida_pagina(pagina)
        if len(dados) != PAGE_SIZE:
            raise ValueError(f"página com {len(dados)} bytes")

        if pagina not in self._paginas:
            # Garante que a página exista no cache antes de modificá-la.
            self.get_page(pagina)

        self._paginas[pagina][:] = dados
        self._paginas.move_to_end(pagina)
        self._dirty.add(pagina)

    def _flush_page(self, pagina: int) -> None:
        #Persiste uma página específica, se ela estiver suja.
        if pagina not in self._dirty:
            return

        self.pager.escreve(pagina, self._paginas[pagina])
        self._dirty.discard(pagina)

    def flush_page(self, pagina: int) -> None:
        #Persiste uma página específica que está no cache.
        self._valida_pagina(pagina)
        if pagina not in self._paginas:
            raise KeyError(f"Página {pagina} não está no cache")
        self._flush_page(pagina)

    def flush(self) -> None:
        #Persiste todas as páginas sujas, sem removê-las do cache.
        for pagina in list(self._dirty):
            self._flush_page(pagina)
        self.pager.sync()

    def evict(self, pagina: int) -> None:
        #Remove uma página do cache, persistindo-a se estiver suja.
        self._valida_pagina(pagina)
        if pagina not in self._paginas:
            return

        self._flush_page(pagina)
        del self._paginas[pagina]

    def clear(self) -> None:
        #Esvazia o cache, persistindo todas as páginas sujas.
        self.flush()
        self._paginas.clear()
        self._dirty.clear()

    def close(self) -> None:
        #Persiste o cache e fecha o Pager associado.
        self.flush()
        self.pager.fecha()

    def __len__(self) -> int:
        return len(self._paginas)

    def contains(self, pagina: int) -> bool:
        #Indica se uma página está atualmente no cache.
        return pagina in self._paginas

    @property
    def dirty_pages(self) -> set[int]:
        #Retorna uma cópia dos identificadores das páginas sujas.
        return set(self._dirty)
