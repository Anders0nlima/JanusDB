"""Operador Sort com suporte a ordenação em memória e ordenação externa (Fase 3)."""
import os
import struct
import tempfile
from typing import Any, List, Optional, Sequence, Tuple

from .cache import PageCache
from .operadores import Operador
from .storage import HEADER_SIZE, PAGE_SIZE, Pager

RUN_HEADER = struct.Struct("<HH12s")  # quantidade (2B), capacidade (2B), reservado (12B)


class ContadorPager(Pager):
    """Subclasse de Pager que contabiliza operações físicas de I/O (leitura e escrita)."""

    def __init__(self, caminho: str):
        super().__init__(caminho)
        self.leituras = 0
        self.escritas = 0

    def le(self, pagina: int) -> bytearray:
        self.leituras += 1
        return super().le(pagina)

    def escreve(self, pagina: int, dados: bytes | bytearray) -> None:
        self.escritas += 1
        super().escreve(pagina, dados)


class InverteComparacao:
    """Invólucro para inverter comparações em ordenação DESC mantendo min-heap."""

    __slots__ = ("valor",)

    def __init__(self, valor: Any):
        self.valor = valor

    def __lt__(self, other: "InverteComparacao") -> bool:
        return other.valor < self.valor

    def __gt__(self, other: "InverteComparacao") -> bool:
        return other.valor > self.valor

    def __eq__(self, other: object) -> bool:
        if isinstance(other, InverteComparacao):
            return self.valor == other.valor
        return False


class ItemHeap:
    """Entrada da fila de prioridade com desempate estável por id_run."""

    __slots__ = ("chave", "id_run", "linha", "leitor")

    def __init__(self, chave: Any, id_run: int, linha: Tuple[Any, ...], leitor: Any = None):
        self.chave = chave
        self.id_run = id_run
        self.linha = linha
        self.leitor = leitor

    def __lt__(self, other: "ItemHeap") -> bool:
        if self.chave < other.chave:
            return True
        if other.chave < self.chave:
            return False
        return self.id_run < other.id_run


class MinHeap:
    """Implementação manual de Min-Heap para intercalação k-way estável."""

    def __init__(self):
        self.itens: List[ItemHeap] = []

    def push(self, item: ItemHeap) -> None:
        self.itens.append(item)
        self._sift_up(len(self.itens) - 1)

    def pop(self) -> Optional[ItemHeap]:
        if not self.itens:
            return None
        top = self.itens[0]
        ultimo = self.itens.pop()
        if self.itens:
            self.itens[0] = ultimo
            self._sift_down(0)
        return top

    def _sift_up(self, idx: int) -> None:
        pai = (idx - 1) // 2
        while idx > 0 and self.itens[idx] < self.itens[pai]:
            self.itens[idx], self.itens[pai] = self.itens[pai], self.itens[idx]
            idx = pai
            pai = (idx - 1) // 2

    def _sift_down(self, idx: int) -> None:
        n = len(self.itens)
        while True:
            menor = idx
            esq = 2 * idx + 1
            dir = 2 * idx + 2
            if esq < n and self.itens[esq] < self.itens[menor]:
                menor = esq
            if dir < n and self.itens[dir] < self.itens[menor]:
                menor = dir
            if menor != idx:
                self.itens[idx], self.itens[menor] = self.itens[menor], self.itens[idx]
                idx = menor
            else:
                break

    def __len__(self) -> int:
        return len(self.itens)

    def __bool__(self) -> bool:
        return len(self.itens) > 0


class CodecLinha:
    """Serializador e desserializador binário de linhas de tamanho fixo."""

    def __init__(self, esquema: Sequence[Any]):
        self.colunas = []
        for item in esquema:
            if hasattr(item, "tipo") and hasattr(item, "tamanho"):
                self.colunas.append((item.tipo.upper(), item.tamanho))
            elif isinstance(item, (tuple, list)):
                if len(item) == 2:
                    self.colunas.append((str(item[0]).upper(), int(item[1])))
                elif len(item) == 3:
                    self.colunas.append((str(item[1]).upper(), int(item[2])))
            elif isinstance(item, str):
                tipo = item.upper()
                if tipo == "INT":
                    self.colunas.append(("INT", 4))
                elif tipo == "BIGINT":
                    self.colunas.append(("BIGINT", 8))
                else:
                    raise ValueError(f"tipo sem tamanho definido: {item}")
            else:
                raise ValueError(f"formato de coluna inválido: {item}")

        self.tamanho_registro = sum(tam for _, tam in self.colunas)

    def codifica(self, linha: Sequence[Any]) -> bytes:
        if len(linha) != len(self.colunas):
            raise ValueError(f"esperava {len(self.colunas)} valores, vieram {len(linha)}")
        partes = []
        for (tipo, tam), val in zip(self.colunas, linha):
            if tipo == "INT":
                partes.append(struct.pack("<I", val))
            elif tipo == "BIGINT":
                partes.append(struct.pack("<q", val))
            elif tipo == "CHAR":
                if isinstance(val, str):
                    b = val.encode("utf-8")
                elif isinstance(val, (bytes, bytearray)):
                    b = bytes(val)
                else:
                    b = str(val).encode("utf-8")
                if len(b) > tam:
                    raise ValueError(f"string excede tamanho máximo de {tam} bytes")
                partes.append(b + b"\0" * (tam - len(b)))
            else:
                raise ValueError(f"tipo não suportado pelo codec: {tipo}")
        return b"".join(partes)

    def decodifica(self, dados: bytes | bytearray) -> Tuple[Any, ...]:
        if len(dados) < self.tamanho_registro:
            raise ValueError(f"dados com {len(dados)} bytes, esperado pelo menos {self.tamanho_registro}")
        offset = 0
        valores = []
        for tipo, tam in self.colunas:
            pedaco = bytes(dados[offset:offset + tam])
            offset += tam
            if tipo == "INT":
                valores.append(struct.unpack("<I", pedaco)[0])
            elif tipo == "BIGINT":
                valores.append(struct.unpack("<q", pedaco)[0])
            elif tipo == "CHAR":
                texto = pedaco.split(b"\0", 1)[0].decode("utf-8")
                valores.append(texto)
            else:
                raise ValueError(f"tipo não suportado pelo codec: {tipo}")
        return tuple(valores)


class DescritorRun:
    """Metadados de localização e dimensão de um run persistido no arquivo temporário."""

    __slots__ = ("inicio", "num_paginas", "total_linhas")

    def __init__(self, inicio: int, num_paginas: int, total_linhas: int):
        self.inicio = inicio
        self.num_paginas = num_paginas
        self.total_linhas = total_linhas


class LeitorRun:
    """Lê registros de um run mantendo a página ativa fixada no PageCache."""

    def __init__(self, cache: PageCache, desc: DescritorRun, codec: CodecLinha):
        self.cache = cache
        self.desc = desc
        self.codec = codec
        self.pagina_atual = desc.inicio
        self.fim_pagina = desc.inicio + desc.num_paginas
        self.slot = 0
        self.qtd_na_pag = 0
        self.buf: Optional[bytearray] = None
        self.linha_atual: Optional[Tuple[Any, ...]] = None
        self._fixada = False

        if desc.total_linhas > 0:
            self._carrega_pagina_atual()

    def _carrega_pagina_atual(self) -> None:
        self.cache.fixa(self.pagina_atual)
        self._fixada = True
        self.buf = self.cache.get_page(self.pagina_atual)
        self.qtd_na_pag, _, _ = RUN_HEADER.unpack_from(self.buf, 0)
        self.slot = 0
        self._le_slot_atual()

    def _le_slot_atual(self) -> None:
        offset = HEADER_SIZE + self.slot * self.codec.tamanho_registro
        dados = bytes(self.buf[offset:offset + self.codec.tamanho_registro])
        self.linha_atual = self.codec.decodifica(dados)

    def avanca(self) -> None:
        if self.linha_atual is None:
            return
        self.slot += 1
        if self.slot < self.qtd_na_pag:
            self._le_slot_atual()
        else:
            if self._fixada:
                self.cache.solta(self.pagina_atual)
                self._fixada = False
            self.pagina_atual += 1
            if self.pagina_atual < self.fim_pagina:
                self._carrega_pagina_atual()
            else:
                self.linha_atual = None

    def fecha(self) -> None:
        if self._fixada:
            self.cache.solta(self.pagina_atual)
            self._fixada = False
        self.linha_atual = None


class Sort(Operador):
    """Operador de ordenação com suporte a ordenação em memória e ordenação externa (2-pass / k-way)."""

    def __init__(
        self,
        filho: Operador,
        coluna_idx: int,
        direcao: str = "ASC",
        mem_paginas: int = 3,
        esquema: Optional[Sequence[Any]] = None,
        caminho_temp: Optional[str] = None,
    ):
        if mem_paginas < 3:
            raise ValueError("mem_paginas deve ser no mínimo 3")
        self.filho = filho
        self.coluna_idx = coluna_idx
        self.direcao = direcao.upper()
        if self.direcao not in ("ASC", "DESC"):
            raise ValueError(f"direção inválida: {direcao}")
        self.mem_paginas = mem_paginas
        self.esquema = esquema
        self.caminho_temp = caminho_temp

        self.codec = CodecLinha(esquema) if esquema is not None else None
        self._linhas_memoria: List[Tuple[Any, ...]] = []
        self._pos_memoria = 0
        self._em_memoria = True

        self.temp_pager: Optional[ContadorPager] = None
        self.temp_cache: Optional[PageCache] = None
        self._temp_arquivo: Optional[str] = None
        self._leitores_ativos: List[LeitorRun] = []
        self._heap: Optional[MinHeap] = None
        self._aberto = False

    def _cria_chave(self, valor: Any) -> Any:
        if self.direcao == "DESC":
            return InverteComparacao(valor)
        return valor

    def _grava_run(self, linhas: List[Tuple[Any, ...]], linhas_por_pagina: int) -> DescritorRun:
        inicio = self.temp_pager.n_paginas
        num_paginas = (len(linhas) + linhas_por_pagina - 1) // linhas_por_pagina
        for i in range(num_paginas):
            pag_id = self.temp_pager.aloca()
            fatia = linhas[i * linhas_por_pagina:(i + 1) * linhas_por_pagina]
            buf = bytearray(PAGE_SIZE)
            RUN_HEADER.pack_into(buf, 0, len(fatia), linhas_por_pagina, b"\0" * 12)
            offset = HEADER_SIZE
            for r in fatia:
                buf[offset:offset + self.codec.tamanho_registro] = self.codec.codifica(r)
                offset += self.codec.tamanho_registro
            self.temp_pager.escreve(pag_id, buf)
        return DescritorRun(inicio, num_paginas, len(linhas))

    def abre(self) -> None:
        self.fecha()
        self.filho.abre()
        self._aberto = True

        # Lê primeiro lote para verificar se cabe em memória
        primeira_linha = self.filho.proximo()
        if primeira_linha is None:
            self._em_memoria = True
            self._linhas_memoria = []
            self._pos_memoria = 0
            return

        if self.codec is None:
            # Se não foi fornecido esquema, infere a partir da primeira tupla
            esq = []
            for val in primeira_linha:
                if isinstance(val, int):
                    esq.append(("INT", 4))
                else:
                    esq.append(("CHAR", max(len(str(val).encode("utf-8")), 20)))
            self.codec = CodecLinha(esq)

        linhas_por_pagina = (PAGE_SIZE - HEADER_SIZE) // self.codec.tamanho_registro
        if linhas_por_pagina < 1:
            linhas_por_pagina = 1
        capacidade_run = self.mem_paginas * linhas_por_pagina

        buffer_inicial = [primeira_linha]
        while len(buffer_inicial) < capacidade_run:
            l = self.filho.proximo()
            if l is None:
                break
            buffer_inicial.append(l)

        # Se após o lote inicial a entrada terminou, cabe em memória!
        prox_linha = self.filho.proximo() if len(buffer_inicial) == capacidade_run else None

        if prox_linha is None:
            self._em_memoria = True
            buffer_inicial.sort(
                key=lambda r: r[self.coluna_idx],
                reverse=(self.direcao == "DESC"),
            )
            self._linhas_memoria = buffer_inicial
            self._pos_memoria = 0
            return

        # NÃO cabe em memória: aciona ordenação externa!
        self._em_memoria = False
        if self.caminho_temp:
            self._temp_arquivo = self.caminho_temp
        else:
            fd, self._temp_arquivo = tempfile.mkstemp(prefix="janusdb_sort_", suffix=".tmp")
            os.close(fd)

        self.temp_pager = ContadorPager(self._temp_arquivo)
        # Fan-in = mem_paginas - 1
        fan_in = self.mem_paginas - 1
        self.temp_cache = PageCache(self.temp_pager, capacidade=fan_in)

        # 1. Fase de geração de runs ordenados
        runs: List[DescritorRun] = []
        lote_atual = buffer_inicial
        lote_atual.append(prox_linha)

        while True:
            while len(lote_atual) < capacidade_run:
                l = self.filho.proximo()
                if l is None:
                    break
                lote_atual.append(l)

            lote_atual.sort(
                key=lambda r: r[self.coluna_idx],
                reverse=(self.direcao == "DESC"),
            )
            runs.append(self._grava_run(lote_atual, linhas_por_pagina))

            l = self.filho.proximo()
            if l is None:
                break
            lote_atual = [l]

        # 2. Fase de intercalação k-way (repetida até restar no máximo fan_in runs)
        while len(runs) > fan_in:
            novos_runs: List[DescritorRun] = []
            for i in range(0, len(runs), fan_in):
                grupo = runs[i:i + fan_in]
                if len(grupo) == 1:
                    novos_runs.append(grupo[0])
                    continue

                leitores = [LeitorRun(self.temp_cache, desc, self.codec) for desc in grupo]
                heap_interm = MinHeap()
                for id_run, leitor in enumerate(leitores):
                    if leitor.linha_atual is not None:
                        ch = self._cria_chave(leitor.linha_atual[self.coluna_idx])
                        heap_interm.push(ItemHeap(ch, id_run, leitor.linha_atual, leitor))

                linhas_novo_run: List[Tuple[Any, ...]] = []
                while heap_interm:
                    item = heap_interm.pop()
                    linhas_novo_run.append(item.linha)
                    item.leitor.avanca()
                    if item.leitor.linha_atual is not None:
                        ch = self._cria_chave(item.leitor.linha_atual[self.coluna_idx])
                        heap_interm.push(ItemHeap(ch, item.id_run, item.leitor.linha_atual, item.leitor))

                for leitor in leitores:
                    leitor.fecha()

                novos_runs.append(self._grava_run(linhas_novo_run, linhas_por_pagina))
            runs = novos_runs

        # 3. Última passada (não é gravada no arquivo: entrega sob demanda via proximo())
        self._leitores_ativos = [LeitorRun(self.temp_cache, desc, self.codec) for desc in runs]
        self._heap = MinHeap()
        for id_run, leitor in enumerate(self._leitores_ativos):
            if leitor.linha_atual is not None:
                ch = self._cria_chave(leitor.linha_atual[self.coluna_idx])
                self._heap.push(ItemHeap(ch, id_run, leitor.linha_atual, leitor))

    def proximo(self) -> Optional[Tuple[Any, ...]]:
        if not self._aberto:
            return None

        if self._em_memoria:
            if self._pos_memoria >= len(self._linhas_memoria):
                return None
            linha = self._linhas_memoria[self._pos_memoria]
            self._pos_memoria += 1
            return linha

        # Modo ordenação externa: extrai do min-heap
        if not self._heap:
            return None

        item = self._heap.pop()
        linha = item.linha
        leitor = item.leitor
        leitor.avanca()
        if leitor.linha_atual is not None:
            ch = self._cria_chave(leitor.linha_atual[self.coluna_idx])
            self._heap.push(ItemHeap(ch, item.id_run, leitor.linha_atual, leitor))
        return linha

    def fecha(self) -> None:
        if self._aberto:
            for leitor in self._leitores_ativos:
                leitor.fecha()
            self._leitores_ativos = []
            self._heap = None

            if self.temp_cache is not None:
                self.temp_cache.close()
                self.temp_cache = None
                self.temp_pager = None
            elif self.temp_pager is not None:
                self.temp_pager.fecha()
                self.temp_pager = None

            if self._temp_arquivo is not None and os.path.exists(self._temp_arquivo):
                try:
                    os.remove(self._temp_arquivo)
                except OSError:
                    pass
                self._temp_arquivo = None

            self._linhas_memoria = []
            self._pos_memoria = 0
            self._aberto = False

        self.filho.fecha()
