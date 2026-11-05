"""Catálogo persistente de tabelas do JanusDB (M4).

O catálogo é uma tabela que descreve as outras tabelas (uma linha por tabela),
armazenada fisicamente na página 1 do arquivo de dados.
Cada registro ocupa 236 bytes:
- nome: CHAR(32)
- primeira: INT (4 bytes, offset da página inicial da tabela)
- colunas: CHAR(200) (definições como 'id INT, matricula INT, nome CHAR(20)')
"""
import os
import struct
from dataclasses import dataclass

from .cache import PageCache
from .storage import HEADER_SIZE, PAGE_SIZE, Pager

PAGINA_CATALOGO = 1
TAM_REGISTRO_CATALOGO = 236
MAGIC = b"JDB4"
HEADER_PAGINA = struct.Struct("<4sHH8s")  # magic (4B), tam_reg (2B), slots_usados (2B), reservado (8B)
CATALOG_RECORD_STRUCT = struct.Struct("<32sI200s")  # nome (32B), primeira (4B), colunas (200B)
MAX_TABELAS_CATALOGO = (PAGE_SIZE - HEADER_SIZE) // TAM_REGISTRO_CATALOGO  # (4096 - 16) // 236 = 17


class ErroSemantico(ValueError):
    """Erro de esquema, tipo, tabela ou coluna."""


@dataclass(frozen=True)
class Coluna:
    nome: str
    tipo: str
    tamanho: int

    def tupla(self):
        return (self.nome, self.tipo, self.tamanho)


@dataclass(frozen=True)
class Tabela:
    nome: str
    colunas: tuple[Coluna, ...]
    pagina: int
    slots_usados: int = 0

    @property
    def tamanho_registro(self) -> int:
        return sum(c.tamanho for c in self.colunas)


def analisa_colunas(texto_colunas: str) -> list[Coluna]:
    """Desserializa a string de colunas do catálogo (ex: 'id INT, nome CHAR(20)')."""
    from .parser import Parser
    from .tokenizer import tokeniza

    p = Parser(tokeniza(texto_colunas))
    cols = [p.coluna()]
    while p.aceita("SIMBOLO", ","):
        cols.append(p.coluna())
    p.espera("FIM")
    return [Coluna(nome, tipo, tam) for nome, tipo, tam in cols]


def formata_colunas(colunas) -> str:
    """Serializa a lista de colunas para string armazenável no catálogo."""
    partes = []
    for c in colunas:
        if isinstance(c, Coluna):
            nome, tipo, tam = c.nome, c.tipo, c.tamanho
        else:
            nome, tipo, tam = c[0], c[1], c[2]
        if tipo.upper() == "INT":
            partes.append(f"{nome} INT")
        else:
            partes.append(f"{nome} CHAR({tam})")
    return ", ".join(partes)


class Catalogo:
    def __init__(self, cache_ou_caminho):
        self._pager_proprio = None
        if isinstance(cache_ou_caminho, str):
            self.caminho = os.path.abspath(cache_ou_caminho)
            self._pager_proprio = Pager(self.caminho)
            self.cache = PageCache(self._pager_proprio)
        elif isinstance(cache_ou_caminho, PageCache):
            self.cache = cache_ou_caminho
            self.caminho = getattr(self.cache.pager.f, "name", "banco.db")
        else:
            raise TypeError("Catalogo espera uma instância de PageCache ou caminho do arquivo")

        self.tabelas: dict[str, Tabela] = {}
        self._garante_pagina_catalogo()
        self._carrega()

    def _garante_pagina_catalogo(self) -> None:
        """Garante que a página 0 e a página 1 (catálogo) existam no arquivo."""
        # Se o arquivo for novo, aloca a página 0 e a página 1 (PAGINA_CATALOGO)
        while self.cache.pager.n_paginas <= PAGINA_CATALOGO:
            self.cache.pager.aloca()

        buf = self.cache.get_page(PAGINA_CATALOGO)
        magic, tam_reg, _, _ = HEADER_PAGINA.unpack_from(buf, 0)
        if magic != MAGIC or tam_reg != TAM_REGISTRO_CATALOGO:
            # Inicializa cabeçalho da página 1 com slots_usados = 0
            HEADER_PAGINA.pack_into(buf, 0, MAGIC, TAM_REGISTRO_CATALOGO, 0, b"\0" * 8)
            self.cache.mark_dirty(PAGINA_CATALOGO)
            self.cache.flush_page(PAGINA_CATALOGO)

    def _carrega(self) -> None:
        """Lê os metadados das tabelas gravados na página 1 do banco."""
        buf = self.cache.get_page(PAGINA_CATALOGO)
        magic, tam_reg, slots_usados, _ = HEADER_PAGINA.unpack_from(buf, 0)
        if magic != MAGIC or tam_reg != TAM_REGISTRO_CATALOGO:
            raise ErroSemantico("página de catálogo corrompida ou inválida")

        offset = HEADER_SIZE
        for _ in range(slots_usados):
            nome_b, primeira, colunas_b = CATALOG_RECORD_STRUCT.unpack_from(buf, offset)
            offset += TAM_REGISTRO_CATALOGO

            nome = nome_b.split(b"\0", 1)[0].decode("utf-8")
            colunas_str = colunas_b.split(b"\0", 1)[0].decode("utf-8")
            if not nome:
                continue
            colunas = tuple(analisa_colunas(colunas_str))
            self.tabelas[nome.casefold()] = Tabela(nome, colunas, primeira)

    def cria_tabela(self, nome: str, colunas, pagina: int) -> Tabela:
        chave = nome.casefold()
        if chave in self.tabelas:
            raise ErroSemantico(f"tabela {nome} já existe")
        if not colunas:
            raise ErroSemantico("uma tabela precisa ter pelo menos uma coluna")

        nomes = [c[0].casefold() if isinstance(c, (tuple, list)) else c.nome.casefold() for c in colunas]
        if len(nomes) != len(set(nomes)):
            raise ErroSemantico("nomes de coluna duplicados")

        objetos = tuple(
            c if isinstance(c, Coluna) else Coluna(str(c[0]), str(c[1]).upper(), int(c[2]))
            for c in colunas
        )
        if sum(c.tamanho for c in objetos) > 4080:
            raise ErroSemantico("registro maior que o espaço disponível em uma página")

        colunas_str = formata_colunas(objetos)
        colunas_bytes = colunas_str.encode("utf-8")
        if len(colunas_bytes) > 200:
            raise ErroSemantico("definição de colunas excede 200 bytes no catálogo")

        nome_bytes = nome.encode("utf-8")
        if len(nome_bytes) > 32:
            raise ErroSemantico("nome da tabela excede 32 bytes no catálogo")

        buf = self.cache.get_page(PAGINA_CATALOGO)
        magic, tam_reg, slots_usados, reservado = HEADER_PAGINA.unpack_from(buf, 0)
        if slots_usados >= MAX_TABELAS_CATALOGO:
            raise ErroSemantico("capacidade do catálogo esgotada (máximo de 17 tabelas)")

        offset = HEADER_SIZE + slots_usados * TAM_REGISTRO_CATALOGO
        reg_nome = nome_bytes + b"\0" * (32 - len(nome_bytes))
        reg_colunas = colunas_bytes + b"\0" * (200 - len(colunas_bytes))
        CATALOG_RECORD_STRUCT.pack_into(buf, offset, reg_nome, pagina, reg_colunas)

        # Incrementa contador de tabelas na página de catálogo
        HEADER_PAGINA.pack_into(buf, 0, magic, tam_reg, slots_usados + 1, reservado)
        self.cache.mark_dirty(PAGINA_CATALOGO)
        self.cache.flush_page(PAGINA_CATALOGO)
        self.cache.pager.sync()

        tabela = Tabela(nome, objetos, pagina, 0)
        self.tabelas[chave] = tabela
        return tabela

    def busca(self, nome: str) -> Tabela:
        try:
            return self.tabelas[nome.casefold()]
        except KeyError as exc:
            raise ErroSemantico(f"tabela {nome} não existe") from exc

    def atualiza_slots(self, nome: str, slots_usados: int):
        """Atualização em memória para compatibilidade com versões anteriores."""
        t = self.busca(nome)
        self.tabelas[nome.casefold()] = Tabela(t.nome, t.colunas, t.pagina, slots_usados)

    def valida_valores(self, tabela: Tabela, valores):
        if len(valores) != len(tabela.colunas):
            raise ErroSemantico(f"esperava {len(tabela.colunas)} valores, vieram {len(valores)}")
        for coluna, valor in zip(tabela.colunas, valores):
            if coluna.tipo == "INT":
                if not isinstance(valor, int) or isinstance(valor, bool) or not (0 <= valor <= 0xFFFFFFFF):
                    raise ErroSemantico(f"coluna {coluna.nome} é INT, veio {valor!r}")
            elif coluna.tipo == "CHAR":
                if not isinstance(valor, str):
                    raise ErroSemantico(f"coluna {coluna.nome} é CHAR({coluna.tamanho}), veio {valor!r}")
                if len(valor.encode("utf-8")) > coluna.tamanho:
                    raise ErroSemantico(f"coluna {coluna.nome} aceita até {coluna.tamanho} bytes")
            else:
                raise ErroSemantico(f"tipo não suportado: {coluna.tipo}")

    def busca_coluna(self, tabela: Tabela, nome: str) -> int:
        for i, coluna in enumerate(tabela.colunas):
            if coluna.nome.casefold() == nome.casefold():
                return i
        raise ErroSemantico(f"coluna {nome} não existe na tabela {tabela.nome}")

    def close(self):
        if self._pager_proprio is not None:
            self.cache.close()
