"""Operador Sort e Codec de Linhas do JanusDB."""
import struct
from typing import Any, List, Optional, Sequence, Tuple

from .operadores import Operador


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


class Sort(Operador):
    """Operador de ordenação (suporta ordenação em memória e externa)."""

    def __init__(
        self,
        filho: Operador,
        coluna_idx: int,
        direcao: str = "ASC",
        mem_paginas: int = 3,
        esquema: Optional[Sequence[Any]] = None,
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
        self.codec = CodecLinha(esquema) if esquema is not None else None
        self._linhas: List[Tuple[Any, ...]] = []
        self._pos = 0
        self._aberto = False

    def abre(self) -> None:
        self.fecha()
        self.filho.abre()
        self._linhas = []

        # Consome todas as linhas do filho
        while True:
            linha = self.filho.proximo()
            if linha is None:
                break
            self._linhas.append(linha)

        # Ordena em memória mantendo a estabilidade
        self._linhas.sort(
            key=lambda r: r[self.coluna_idx],
            reverse=(self.direcao == "DESC"),
        )

        self._pos = 0
        self._aberto = True

    def proximo(self) -> Optional[Tuple[Any, ...]]:
        if not self._aberto:
            return None
        if self._pos >= len(self._linhas):
            return None
        linha = self._linhas[self._pos]
        self._pos += 1
        return linha

    def fecha(self) -> None:
        if self._aberto:
            self._linhas = []
            self._pos = 0
            self._aberto = False
        self.filho.fecha()
