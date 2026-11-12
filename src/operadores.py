"""Modelo de execução por iteradores (Volcano Iterator Model)."""
from abc import ABC, abstractmethod
import struct
from typing import Any, Optional, Tuple

from .cache import PageCache
from .catalog import Tabela
from .storage import HEADER_SIZE, PAGE_SIZE

MAGIC = b"JDB4"
HEADER = struct.Struct("<4sHHI4s")
DATA_START = HEADER_SIZE


class Operador(ABC):
    @abstractmethod
    def abre(self) -> None:
        """Inicializa o operador e seus recursos."""
        pass

    @abstractmethod
    def proximo(self) -> Optional[Tuple[Any, ...]]:
        """Retorna a próxima tupla de dados, ou None ao atingir o fim da iteração."""
        pass

    @abstractmethod
    def fecha(self) -> None:
        """Libera recursos, alfinetes (pins) e arquivos temporários."""
        pass

    def __enter__(self):
        self.abre()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.fecha()

    def __iter__(self):
        while True:
            linha = self.proximo()
            if linha is None:
                break
            yield linha


class SeqScan(Operador):
    """Varre sequencialmente as páginas encadeadas de uma tabela."""

    def __init__(self, cache: PageCache, tabela: Tabela):
        self.cache = cache
        self.tabela = tabela
        self._pagina_atual = 0
        self._slot_atual = 0
        self._quantidade = 0
        self._proxima_pagina = 0
        self._offset = DATA_START
        self._aberto = False

    def abre(self) -> None:
        self.fecha()
        self._pagina_atual = self.tabela.pagina
        self._slot_atual = 0
        self._quantidade = 0
        self._proxima_pagina = 0
        self._offset = DATA_START
        self._aberto = True
        if self._pagina_atual != 0:
            self._carrega_pagina()

    def _carrega_pagina(self) -> None:
        self.cache.fixa(self._pagina_atual)
        buf = self.cache.get_page(self._pagina_atual)
        magic, tamanho, self._quantidade, self._proxima_pagina, _ = HEADER.unpack_from(buf, 0)
        if magic != MAGIC or tamanho != self.tabela.tamanho_registro:
            raise ValueError(f"página de dados {self._pagina_atual} inválida para a tabela {self.tabela.nome}")
        self._slot_atual = 0
        self._offset = DATA_START

    def proximo(self) -> Optional[Tuple[Any, ...]]:
        if not self._aberto or self._pagina_atual == 0:
            return None

        while self._slot_atual >= self._quantidade:
            self.cache.solta(self._pagina_atual)
            if self._proxima_pagina != 0:
                self._pagina_atual = self._proxima_pagina
                self._carrega_pagina()
            else:
                self._pagina_atual = 0
                return None

        buf = self.cache.get_page(self._pagina_atual)
        valores = []
        for coluna in self.tabela.colunas:
            bruto = bytes(buf[self._offset:self._offset + coluna.tamanho])
            self._offset += coluna.tamanho
            if coluna.tipo == "INT":
                valores.append(struct.unpack("<I", bruto)[0])
            else:
                texto = bruto.split(b"\0", 1)[0]
                valores.append(texto.decode("utf-8"))

        self._slot_atual += 1
        return tuple(valores)

    def fecha(self) -> None:
        if self._aberto:
            if self._pagina_atual != 0:
                self.cache.solta(self._pagina_atual)
                self._pagina_atual = 0
            self._aberto = False


class Filter(Operador):
    """Filtra registros que satisfazem a condição de igualdade."""

    def __init__(self, filho: Operador, coluna_idx: int, esperado: Any):
        self.filho = filho
        self.coluna_idx = coluna_idx
        self.esperado = esperado

    def abre(self) -> None:
        self.filho.abre()

    def proximo(self) -> Optional[Tuple[Any, ...]]:
        while True:
            linha = self.filho.proximo()
            if linha is None:
                return None
            if linha[self.coluna_idx] == self.esperado:
                return linha

    def fecha(self) -> None:
        self.filho.fecha()


class Project(Operador):
    """Projeta um subconjunto ordenado de colunas."""

    def __init__(self, filho: Operador, indices: list[int]):
        self.filho = filho
        self.indices = indices

    def abre(self) -> None:
        self.filho.abre()

    def proximo(self) -> Optional[Tuple[Any, ...]]:
        linha = self.filho.proximo()
        if linha is None:
            return None
        return tuple(linha[i] for i in self.indices)

    def fecha(self) -> None:
        self.filho.fecha()
