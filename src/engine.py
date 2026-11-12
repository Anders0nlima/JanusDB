"""Execução inicial dos comandos SQL do M4 sobre Pager e PageCache."""
import os
import struct

from .cache import PageCache
from .catalog import Catalogo, ErroSemantico, Tabela
from .operadores import Filter, Project, SeqScan
from .parser import analisa
from .storage import HEADER_SIZE, PAGE_SIZE, Pager

MAGIC = b"JDB4"
HEADER = struct.Struct("<4sHHI4s")  # magic, tamanho do registro, slots ocupados, proxima_pagina, reservado
DATA_START = HEADER_SIZE


class Engine:
    def __init__(self, caminho: str, capacidade_cache: int = 8):
        pasta = os.path.dirname(os.path.abspath(caminho))
        os.makedirs(pasta, exist_ok=True)
        self.caminho = caminho
        self.pager = Pager(caminho)
        self.cache = PageCache(self.pager, capacidade=capacidade_cache)
        self.catalogo = Catalogo(self.cache)

    def _inicializa_pagina_tabela(self, pagina: int, tamanho_registro: int, proxima_pagina: int = 0):
        buf = self.cache.get_page(pagina)
        HEADER.pack_into(buf, 0, MAGIC, tamanho_registro, 0, proxima_pagina, b"\0" * 4)
        self.cache.mark_dirty(pagina)

    def _le_registros(self, tabela: Tabela):
        registros = []
        total_quantidade = 0
        pagina_atual = tabela.pagina
        capacidade = 0

        while pagina_atual != 0:
            buf = self.cache.get_page(pagina_atual)
            magic, tamanho, quantidade, proxima, _ = HEADER.unpack_from(buf, 0)
            if magic != MAGIC or tamanho != tabela.tamanho_registro:
                raise ErroSemantico(f"página de dados {pagina_atual} inválida para a tabela {tabela.nome}")
            capacidade = (PAGE_SIZE - DATA_START) // tamanho
            if quantidade > capacidade:
                raise ErroSemantico(f"cabeçalho da página {pagina_atual} contém quantidade de registros inválida")
            offset = DATA_START
            for _ in range(quantidade):
                valores = []
                for coluna in tabela.colunas:
                    bruto = bytes(buf[offset:offset + coluna.tamanho])
                    offset += coluna.tamanho
                    if coluna.tipo == "INT":
                        valores.append(struct.unpack("<I", bruto)[0])
                    else:
                        texto = bruto.split(b"\0", 1)[0]
                        valores.append(texto.decode("utf-8"))
                registros.append(valores)
            total_quantidade += quantidade
            pagina_atual = proxima

        return registros, total_quantidade, capacidade

    def _insere(self, tabela: Tabela, valores):
        self.catalogo.valida_valores(tabela, valores)
        pagina_atual = tabela.pagina
        while True:
            buf = self.cache.get_page(pagina_atual)
            magic, tamanho, quantidade, proxima, reservado = HEADER.unpack_from(buf, 0)
            if magic != MAGIC or tamanho != tabela.tamanho_registro:
                raise ErroSemantico(f"página de dados {pagina_atual} inválida para a tabela {tabela.nome}")
            if proxima == 0:
                break
            pagina_atual = proxima

        capacidade = (PAGE_SIZE - DATA_START) // tamanho
        if quantidade < capacidade:
            offset = DATA_START + quantidade * tabela.tamanho_registro
            for coluna, valor in zip(tabela.colunas, valores):
                if coluna.tipo == "INT":
                    bruto = struct.pack("<I", valor)
                else:
                    codificado = valor.encode("utf-8")
                    bruto = codificado + b"\0" * (coluna.tamanho - len(codificado))
                buf[offset:offset + coluna.tamanho] = bruto
                offset += coluna.tamanho
            HEADER.pack_into(buf, 0, magic, tamanho, quantidade + 1, proxima, reservado)
            self.cache.mark_dirty(pagina_atual)
            self.cache.flush_page(pagina_atual)
            self.pager.sync()
            return "OK 1"
        else:
            nova_pagina = self.pager.aloca()
            self._inicializa_pagina_tabela(nova_pagina, tamanho, proxima_pagina=0)
            buf_nova = self.cache.get_page(nova_pagina)
            offset = DATA_START
            for coluna, valor in zip(tabela.colunas, valores):
                if coluna.tipo == "INT":
                    bruto = struct.pack("<I", valor)
                else:
                    codificado = valor.encode("utf-8")
                    bruto = codificado + b"\0" * (coluna.tamanho - len(codificado))
                buf_nova[offset:offset + coluna.tamanho] = bruto
                offset += coluna.tamanho

            HEADER.pack_into(buf_nova, 0, MAGIC, tamanho, 1, 0, b"\0" * 4)
            self.cache.mark_dirty(nova_pagina)

            HEADER.pack_into(buf, 0, magic, tamanho, quantidade, nova_pagina, reservado)
            self.cache.mark_dirty(pagina_atual)

            self.cache.flush_page(pagina_atual)
            self.cache.flush_page(nova_pagina)
            self.pager.sync()
            return "OK 1"

    def executa(self, sql: str):
        arvore = analisa(sql)
        op = arvore["op"]
        if op == "CREATE":
            # Valida metadados antes de alocar uma página para reduzir páginas órfãs.
            if arvore["tabela"].casefold() in self.catalogo.tabelas:
                raise ErroSemantico(f"tabela {arvore['tabela']} já existe")
            nomes = [c[0].casefold() for c in arvore["colunas"]]
            if len(nomes) != len(set(nomes)):
                raise ErroSemantico("nomes de coluna duplicados")
            if sum(c[2] for c in arvore["colunas"]) > PAGE_SIZE - DATA_START:
                raise ErroSemantico("registro maior que o espaço disponível em uma página")
            pagina = self.pager.aloca()
            tamanho = sum(c[2] for c in arvore["colunas"])
            self._inicializa_pagina_tabela(pagina, tamanho)
            self.cache.flush_page(pagina)
            self.pager.sync()
            self.catalogo.cria_tabela(arvore["tabela"], arvore["colunas"], pagina)
            return "OK"
        tabela = self.catalogo.busca(arvore["tabela"])
        if op == "INSERT":
            return self._insere(tabela, arvore["valores"])
        if op == "SELECT":
            op_atual = SeqScan(self.cache, tabela)
            try:
                if arvore["where"] is not None:
                    nome_coluna, esperado = arvore["where"]
                    idx_where = self.catalogo.busca_coluna(tabela, nome_coluna)
                    coluna = tabela.colunas[idx_where]
                    if coluna.tipo == "INT" and not isinstance(esperado, int):
                        raise ErroSemantico(f"coluna {coluna.nome} é INT, veio {esperado!r}")
                    if coluna.tipo == "CHAR" and not isinstance(esperado, str):
                        raise ErroSemantico(f"coluna {coluna.nome} é CHAR, veio {esperado!r}")
                    op_atual = Filter(op_atual, idx_where, esperado)

                if arvore["colunas"] == ["*"]:
                    indices = list(range(len(tabela.colunas)))
                else:
                    indices = [self.catalogo.busca_coluna(tabela, n) for n in arvore["colunas"]]

                op_atual = Project(op_atual, indices)

                linhas = []
                op_atual.abre()
                while True:
                    linha = op_atual.proximo()
                    if linha is None:
                        break
                    linhas.append("|".join(str(val) for val in linha))
            finally:
                op_atual.fecha()

            sufixo_linha = "linha" if len(linhas) == 1 else "linhas"
            return "\n".join(linhas + [f"({len(linhas)} {sufixo_linha})"])
        raise ErroSemantico(f"operação não suportada: {op}")

    def close(self):
        self.cache.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
