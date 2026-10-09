from bisect import bisect_left, bisect_right
import struct

from .cache import PageCache
from .storage import PAGE_SIZE

# Tipos de nó
NODE_INTERNAL = 0
NODE_LEAF = 1

# Geometria do cabeçalho
NODE_HEADER_SIZE = 16
# Format: tipo (B=1B), num_chaves (H=2B), proxima_pagina (I=4B), reservados (9s=9B) -> 16 bytes
HEADER_STRUCT = struct.Struct("<BHI9s")

# Formatos de entradas
ENTRY_STRUCT = struct.Struct("<II")  # chave (4B), valor ou filho (4B)
CHILD_PTR_STRUCT = struct.Struct("<I")  # ponteiro para página filha (4B)

ENTRY_SIZE = 8
CHILD_PTR_SIZE = 4

# Capacidades máximas suportadas fisicamente por uma página de 4096 bytes:
# Folha: (4096 - 16) / 8 = 510 entradas
DEFAULT_MAX_LEAF_KEYS = (PAGE_SIZE - NODE_HEADER_SIZE) // ENTRY_SIZE
# Interno: (4096 - 16 - 4) / 8 = 509 entradas
DEFAULT_MAX_INTERNAL_KEYS = (PAGE_SIZE - NODE_HEADER_SIZE - CHILD_PTR_SIZE) // ENTRY_SIZE


def cria_no_folha(buf: bytearray, proxima_pagina: int = 0) -> None:
    """Inicializa um buffer de página como um nó folha vazio."""
    HEADER_STRUCT.pack_into(buf, 0, NODE_LEAF, 0, proxima_pagina, b"\x00" * 9)


def cria_no_interno(buf: bytearray, primeiro_filho: int) -> None:
    """Inicializa um buffer de página como um nó interno com o primeiro filho."""
    HEADER_STRUCT.pack_into(buf, 0, NODE_INTERNAL, 0, 0, b"\x00" * 9)
    CHILD_PTR_STRUCT.pack_into(buf, NODE_HEADER_SIZE, primeiro_filho)


def le_cabecalho_no(buf: bytearray) -> tuple[int, int, int]:
    """Retorna (tipo_no, num_chaves, proxima_pagina)."""
    tipo_no, num_chaves, proxima_pagina, _ = HEADER_STRUCT.unpack_from(buf, 0)
    return tipo_no, num_chaves, proxima_pagina


def grava_cabecalho_no(buf: bytearray, tipo_no: int, num_chaves: int, proxima_pagina: int = 0) -> None:
    """Atualiza os campos do cabeçalho de um nó."""
    HEADER_STRUCT.pack_into(buf, 0, tipo_no, num_chaves, proxima_pagina, b"\x00" * 9)


def le_entradas_folha(buf: bytearray) -> list[tuple[int, int]]:
    """Lê todas as entradas (chave, valor) de um nó folha."""
    _, num_chaves, _ = le_cabecalho_no(buf)
    entradas = []
    offset = NODE_HEADER_SIZE
    for _ in range(num_chaves):
        chave, valor = ENTRY_STRUCT.unpack_from(buf, offset)
        entradas.append((chave, valor))
        offset += ENTRY_SIZE
    return entradas


def grava_entradas_folha(buf: bytearray, entradas: list[tuple[int, int]], proxima_pagina: int = 0) -> None:
    """Sobrescreve as entradas de um nó folha e atualiza seu cabeçalho."""
    grava_cabecalho_no(buf, NODE_LEAF, len(entradas), proxima_pagina)
    offset = NODE_HEADER_SIZE
    for chave, valor in entradas:
        ENTRY_STRUCT.pack_into(buf, offset, chave, valor)
        offset += ENTRY_SIZE


def le_entradas_interno(buf: bytearray) -> tuple[int, list[tuple[int, int]]]:
    """Lê o primeiro filho e todas as entradas (chave, filho) de um nó interno."""
    _, num_chaves, _ = le_cabecalho_no(buf)
    primeiro_filho = CHILD_PTR_STRUCT.unpack_from(buf, NODE_HEADER_SIZE)[0]
    entradas = []
    offset = NODE_HEADER_SIZE + CHILD_PTR_SIZE
    for _ in range(num_chaves):
        chave, filho = ENTRY_STRUCT.unpack_from(buf, offset)
        entradas.append((chave, filho))
        offset += ENTRY_SIZE
    return primeiro_filho, entradas


def grava_entradas_interno(buf: bytearray, primeiro_filho: int, entradas: list[tuple[int, int]]) -> None:
    """Sobrescreve as entradas de um nó interno e atualiza seu cabeçalho."""
    grava_cabecalho_no(buf, NODE_INTERNAL, len(entradas), 0)
    CHILD_PTR_STRUCT.pack_into(buf, NODE_HEADER_SIZE, primeiro_filho)
    offset = NODE_HEADER_SIZE + CHILD_PTR_SIZE
    for chave, filho in entradas:
        ENTRY_STRUCT.pack_into(buf, offset, chave, filho)
        offset += ENTRY_SIZE


class BPlusTree:
    """Árvore B+ que armazena pares (chave: int, valor: int) sobre um :class:`PageCache`."""

    def __init__(
        self,
        cache: PageCache,
        root_page_id: int = 0,
        max_leaf_keys: int = DEFAULT_MAX_LEAF_KEYS,
        max_internal_keys: int = DEFAULT_MAX_INTERNAL_KEYS,
    ):
        if max_leaf_keys < 2:
            raise ValueError("max_leaf_keys deve ser no mínimo 2")
        if max_internal_keys < 2:
            raise ValueError("max_internal_keys deve ser no mínimo 2")

        self.cache = cache
        self.max_leaf_keys = min(max_leaf_keys, DEFAULT_MAX_LEAF_KEYS)
        self.max_internal_keys = min(max_internal_keys, DEFAULT_MAX_INTERNAL_KEYS)
        self.root_page_id = root_page_id

        # Se o arquivo do banco for novo (sem páginas alocadas), cria a raiz como nó folha vazio
        if self.cache.pager.n_paginas == 0:
            root_id = self.cache.pager.aloca()
            buf = self.cache.get_page(root_id)
            cria_no_folha(buf)
            self.cache.mark_dirty(root_id)
            self.root_page_id = root_id
        else:
            # Garante que a raiz exista e seja válida
            if self.root_page_id >= self.cache.pager.n_paginas:
                raise ValueError(f"root_page_id {self.root_page_id} não existe no arquivo")

    def search(self, chave: int) -> int | None:
        """Busca o valor associado à chave na Árvore B+. Retorna None se não encontrada."""
        if not isinstance(chave, int) or isinstance(chave, bool) or chave < 0:
            raise ValueError(f"Chave inválida: {chave}")

        curr_id = self.root_page_id

        while True:
            buf = self.cache.get_page(curr_id)
            tipo_no, _, _ = le_cabecalho_no(buf)

            if tipo_no == NODE_LEAF:
                entradas = le_entradas_folha(buf)
                chaves = [k for k, _ in entradas]
                idx = bisect_left(chaves, chave)
                if idx < len(chaves) and chaves[idx] == chave:
                    return entradas[idx][1]
                return None
            else:
                primeiro_filho, entradas = le_entradas_interno(buf)
                chaves = [k for k, _ in entradas]
                idx = bisect_right(chaves, chave)
                if idx == 0:
                    curr_id = primeiro_filho
                else:
                    curr_id = entradas[idx - 1][1]

    def insert(self, chave: int, valor: int) -> None:
        """Insere ou atualiza o par (chave, valor) na Árvore B+."""
        if not isinstance(chave, int) or isinstance(chave, bool) or chave < 0:
            raise ValueError(f"Chave inválida: {chave}")
        if not isinstance(valor, int) or isinstance(valor, bool) or valor < 0:
            raise ValueError(f"Valor inválido: {valor}")

        parent_stack: list[int] = []
        curr_id = self.root_page_id

        # 1. Desce até encontrar o nó folha adequado
        while True:
            buf = self.cache.get_page(curr_id)
            tipo_no, _, _ = le_cabecalho_no(buf)

            if tipo_no == NODE_LEAF:
                break

            parent_stack.append(curr_id)
            primeiro_filho, entradas = le_entradas_interno(buf)
            chaves = [k for k, _ in entradas]
            idx = bisect_right(chaves, chave)
            if idx == 0:
                curr_id = primeiro_filho
            else:
                curr_id = entradas[idx - 1][1]

        # 2. Inserção na folha
        leaf_buf = self.cache.get_page(curr_id)
        _, _, proxima_pagina = le_cabecalho_no(leaf_buf)
        entradas = le_entradas_folha(leaf_buf)
        chaves = [k for k, _ in entradas]
        idx = bisect_left(chaves, chave)

        # Se a chave já existir, atualiza o valor
        if idx < len(chaves) and chaves[idx] == chave:
            entradas[idx] = (chave, valor)
            grava_entradas_folha(leaf_buf, entradas, proxima_pagina)
            self.cache.mark_dirty(curr_id)
            return

        # Insere a nova entrada mantendo a ordenação
        entradas.insert(idx, (chave, valor))

        # 3. Se couber na folha, salva e encerra
        if len(entradas) <= self.max_leaf_keys:
            grava_entradas_folha(leaf_buf, entradas, proxima_pagina)
            self.cache.mark_dirty(curr_id)
            return

        # 4. Folha cheia: Split de nó folha!
        mid = len(entradas) // 2
        entradas_esquerda = entradas[:mid]
        entradas_direita = entradas[mid:]
        chave_promovida = entradas_direita[0][0]

        # Aloca nova página para a folha direita
        novo_folha_id = self.cache.pager.aloca()
        novo_folha_buf = self.cache.get_page(novo_folha_id)

        # A nova folha aponta para quem a folha antiga apontava
        grava_entradas_folha(novo_folha_buf, entradas_direita, proxima_pagina)
        self.cache.mark_dirty(novo_folha_id)

        # A folha antiga passa a apontar para a nova folha
        grava_entradas_folha(leaf_buf, entradas_esquerda, novo_folha_id)
        self.cache.mark_dirty(curr_id)

        # Promove a menor chave da folha direita para o nó pai
        self._insert_into_parent(curr_id, chave_promovida, novo_folha_id, parent_stack)

    def _insert_into_parent(
        self,
        filho_esquerdo: int,
        chave: int,
        filho_direito: int,
        parent_stack: list[int],
    ) -> None:
        """Insere a chave promotora e o novo filho no nó pai, propagando splits se necessário."""
        # Caso base: a divisão ocorreu na própria raiz! Cria uma nova raiz interna
        if not parent_stack:
            nova_raiz_id = self.cache.pager.aloca()
            nova_raiz_buf = self.cache.get_page(nova_raiz_id)
            cria_no_interno(nova_raiz_buf, primeiro_filho=filho_esquerdo)
            grava_entradas_interno(nova_raiz_buf, primeiro_filho=filho_esquerdo, entradas=[(chave, filho_direito)])
            self.cache.mark_dirty(nova_raiz_id)
            self.root_page_id = nova_raiz_id
            return

        pai_id = parent_stack.pop()
        pai_buf = self.cache.get_page(pai_id)
        primeiro_filho, entradas = le_entradas_interno(pai_buf)

        # Insere a nova chave e ponteiro na posição ordenada correta
        chaves = [k for k, _ in entradas]
        idx = bisect_left(chaves, chave)
        entradas.insert(idx, (chave, filho_direito))

        # Se couber no nó interno, atualiza e encerra
        if len(entradas) <= self.max_internal_keys:
            grava_entradas_interno(pai_buf, primeiro_filho, entradas)
            self.cache.mark_dirty(pai_id)
            return

        # Nó interno cheio: Split de nó interno!
        mid = len(entradas) // 2
        entradas_esquerda = entradas[:mid]
        # Na Árvore B+, a chave promotora do nó interno NÃO fica duplicada em baixo: sobe para o nível superior!
        chave_promovida_pai, novo_primeiro_filho = entradas[mid]
        entradas_direita = entradas[mid + 1 :]

        # Aloca nova página para o nó interno direito
        novo_interno_id = self.cache.pager.aloca()
        novo_interno_buf = self.cache.get_page(novo_interno_id)
        grava_entradas_interno(novo_interno_buf, novo_primeiro_filho, entradas_direita)
        self.cache.mark_dirty(novo_interno_id)

        # Atualiza o nó interno esquerdo
        grava_entradas_interno(pai_buf, primeiro_filho, entradas_esquerda)
        self.cache.mark_dirty(pai_id)

        # Propaga a chave que subiu recursivamente para o pai do pai
        self._insert_into_parent(pai_id, chave_promovida_pai, novo_interno_id, parent_stack)

    def range_search(self, inicio: int, fim: int) -> list[tuple[int, int]]:
        """Retorna todos os pares (chave, valor) no intervalo [inicio, fim], inclusive."""
        if inicio > fim:
            return []

        # 1. Encontra a folha onde 'inicio' começaria
        curr_id = self.root_page_id
        while True:
            buf = self.cache.get_page(curr_id)
            tipo_no, _, _ = le_cabecalho_no(buf)
            if tipo_no == NODE_LEAF:
                break
            primeiro_filho, entradas = le_entradas_interno(buf)
            chaves = [k for k, _ in entradas]
            idx = bisect_right(chaves, inicio)
            if idx == 0:
                curr_id = primeiro_filho
            else:
                curr_id = entradas[idx - 1][1]

        # 2. Percorre horizontalmente através dos ponteiros proxima_pagina
        resultado = []
        while True:
            buf = self.cache.get_page(curr_id)
            _, _, proxima_pagina = le_cabecalho_no(buf)
            entradas = le_entradas_folha(buf)

            for k, v in entradas:
                if k > fim:
                    return resultado
                if k >= inicio:
                    resultado.append((k, v))

            if proxima_pagina == 0:
                break
            curr_id = proxima_pagina

        return resultado

    def items(self) -> list[tuple[int, int]]:
        """Retorna todos os pares (chave, valor) da árvore em ordem crescente."""
        # Encontra a folha mais à esquerda descendo sempre pelo primeiro filho
        curr_id = self.root_page_id
        while True:
            buf = self.cache.get_page(curr_id)
            tipo_no, _, _ = le_cabecalho_no(buf)
            if tipo_no == NODE_LEAF:
                break
            primeiro_filho, _ = le_entradas_interno(buf)
            curr_id = primeiro_filho

        resultado = []
        while True:
            buf = self.cache.get_page(curr_id)
            _, _, proxima_pagina = le_cabecalho_no(buf)
            resultado.extend(le_entradas_folha(buf))
            if proxima_pagina == 0:
                break
            curr_id = proxima_pagina

        return resultado

    def flush(self) -> None:
        """Garante a persistência física de todas as modificações no disco."""
        self.cache.flush()
