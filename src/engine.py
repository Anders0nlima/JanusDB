"""Execução inicial dos comandos SQL do M4 sobre Pager e PageCache."""
import os
import struct

from .cache import PageCache
from .catalog import Catalogo, ErroSemantico, Tabela
from .parser import analisa
from .storage import HEADER_SIZE, PAGE_SIZE, Pager

MAGIC = b"JDB4"
HEADER = struct.Struct("<4sHH8s")  # magic, tamanho do registro, slots ocupados, reservado
DATA_START = HEADER_SIZE


class Engine:
    def __init__(self, caminho: str, capacidade_cache: int = 8):
        pasta = os.path.dirname(os.path.abspath(caminho))
        os.makedirs(pasta, exist_ok=True)
        self.caminho = caminho
        self.pager = Pager(caminho)
        self.cache = PageCache(self.pager, capacidade=capacidade_cache)
        self.catalogo = Catalogo(caminho)

    def _inicializa_pagina_tabela(self, pagina: int, tamanho_registro: int):
        buf = self.cache.get_page(pagina)
        HEADER.pack_into(buf, 0, MAGIC, tamanho_registro, 0, b"\0" * 8)
        self.cache.mark_dirty(pagina)

    def _le_registros(self, tabela: Tabela):
        buf = self.cache.get_page(tabela.pagina)
        magic, tamanho, quantidade, _ = HEADER.unpack_from(buf, 0)
        if magic != MAGIC or tamanho != tabela.tamanho_registro:
            raise ErroSemantico(f"página de dados inválida para a tabela {tabela.nome}")
        capacidade = (PAGE_SIZE - DATA_START) // tamanho
        if quantidade > capacidade:
            raise ErroSemantico("cabeçalho da página contém quantidade de registros inválida")
        registros = []
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
        return registros, quantidade, capacidade

    def _insere(self, tabela: Tabela, valores):
        self.catalogo.valida_valores(tabela, valores)
        registros, quantidade, capacidade = self._le_registros(tabela)
        if quantidade >= capacidade:
            raise ErroSemantico(
                f"a página da tabela {tabela.nome} está cheia ({capacidade} registros); páginas múltiplas ficam para o M5"
            )
        buf = self.cache.get_page(tabela.pagina)
        offset = DATA_START + quantidade * tabela.tamanho_registro
        for coluna, valor in zip(tabela.colunas, valores):
            if coluna.tipo == "INT":
                bruto = struct.pack("<I", valor)
            else:
                codificado = valor.encode("utf-8")
                bruto = codificado + b"\0" * (coluna.tamanho - len(codificado))
            buf[offset:offset + coluna.tamanho] = bruto
            offset += coluna.tamanho
        magic, tamanho, _, reservado = HEADER.unpack_from(buf, 0)
        HEADER.pack_into(buf, 0, magic, tamanho, quantidade + 1, reservado)
        self.cache.mark_dirty(tabela.pagina)
        self.cache.flush_page(tabela.pagina)
        self.catalogo.atualiza_slots(tabela.nome, quantidade + 1)
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
            self.catalogo.cria_tabela(arvore["tabela"], arvore["colunas"], pagina)
            return "OK"
        tabela = self.catalogo.busca(arvore["tabela"])
        if op == "INSERT":
            return self._insere(tabela, arvore["valores"])
        if op == "SELECT":
            registros, _, _ = self._le_registros(tabela)
            if arvore["where"] is not None:
                nome_coluna, esperado = arvore["where"]
                idx_where = self.catalogo.busca_coluna(tabela, nome_coluna)
                coluna = tabela.colunas[idx_where]
                if coluna.tipo == "INT" and not isinstance(esperado, int):
                    raise ErroSemantico(f"coluna {coluna.nome} é INT, veio {esperado!r}")
                if coluna.tipo == "CHAR" and not isinstance(esperado, str):
                    raise ErroSemantico(f"coluna {coluna.nome} é CHAR, veio {esperado!r}")
                registros = [r for r in registros if r[idx_where] == esperado]
            if arvore["colunas"] == ["*"]:
                indices = list(range(len(tabela.colunas)))
            else:
                indices = [self.catalogo.busca_coluna(tabela, n) for n in arvore["colunas"]]
            linhas = ["|".join(str(registro[i]) for i in indices) for registro in registros]
            return "\n".join(linhas + [f"({len(linhas)} linhas)"])
        raise ErroSemantico(f"operação não suportada: {op}")

    def close(self):
        self.cache.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
