"""Operador de agregação por hash (COUNT, SUM e GROUP BY) do JanusDB."""
from typing import Any, List, Optional, Sequence, Tuple

from .operadores import Operador


class Aggregate(Operador):
    """Operador de agregação por hash em memória."""

    def __init__(
        self,
        filho: Operador,
        agregados: Sequence[Tuple[str, Optional[int]]],
        group_by_idx: Optional[int] = None,
    ):
        self.filho = filho
        self.agregados = list(agregados)  # Lista de (tipo, col_idx): e.g. [("COUNT", None), ("SUM", 2)]
        self.group_by_idx = group_by_idx
        self._linhas: List[Tuple[Any, ...]] = []
        self._pos = 0
        self._aberto = False

    def abre(self) -> None:
        self.fecha()
        self.filho.abre()
        self._aberto = True

        grupos = {}
        has_rows = False

        while True:
            linha = self.filho.proximo()
            if linha is None:
                break
            has_rows = True

            chave = linha[self.group_by_idx] if self.group_by_idx is not None else None

            if chave not in grupos:
                grupos[chave] = [0 for _ in self.agregados]

            for i, (tipo, col_idx) in enumerate(self.agregados):
                if tipo == "COUNT":
                    grupos[chave][i] += 1
                elif tipo == "SUM":
                    grupos[chave][i] += linha[col_idx]

        # Tratamento de tabela vazia
        if not has_rows:
            if self.group_by_idx is None:
                # Sem GROUP BY: COUNT(*) é 0, SUM é 0
                grupos[None] = [0 for _ in self.agregados]
            else:
                # Com GROUP BY sobre tabela vazia: devolve 0 linhas
                grupos = {}

        self._linhas = []
        for chave, acumuladores in grupos.items():
            if self.group_by_idx is not None:
                self._linhas.append((chave, *acumuladores))
            else:
                self._linhas.append(tuple(acumuladores))

        self._pos = 0

    def proximo(self) -> Optional[Tuple[Any, ...]]:
        if not self._aberto or self._pos >= len(self._linhas):
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
