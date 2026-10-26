"""Catálogo persistente de tabelas do JanusDB."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass


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


class Catalogo:
    def __init__(self, caminho_dados: str):
        self.caminho = os.path.abspath(caminho_dados) + ".catalog.json"
        self.tabelas: dict[str, Tabela] = {}
        if os.path.exists(self.caminho):
            try:
                with open(self.caminho, "r", encoding="utf-8") as f:
                    bruto = json.load(f)
                for chave, item in bruto.get("tabelas", {}).items():
                    colunas = tuple(Coluna(**c) for c in item["colunas"])
                    self.tabelas[chave.casefold()] = Tabela(
                        nome=item["nome"], colunas=colunas,
                        pagina=int(item["pagina"]), slots_usados=int(item.get("slots_usados", 0)),
                    )
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise ErroSemantico(f"catálogo corrompido ou ilegível: {exc}") from exc

    def salva(self):
        pasta = os.path.dirname(self.caminho) or "."
        os.makedirs(pasta, exist_ok=True)
        dados = {"versao": 1, "tabelas": {
            chave: {"nome": t.nome, "colunas": [asdict(c) for c in t.colunas],
                    "pagina": t.pagina, "slots_usados": t.slots_usados}
            for chave, t in self.tabelas.items()
        }}
        fd, temporario = tempfile.mkstemp(prefix="catalogo_", suffix=".tmp", dir=pasta, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporario, self.caminho)
        finally:
            if os.path.exists(temporario):
                os.unlink(temporario)

    def cria_tabela(self, nome: str, colunas, pagina: int) -> Tabela:
        chave = nome.casefold()
        if chave in self.tabelas:
            raise ErroSemantico(f"tabela {nome} já existe")
        if not colunas:
            raise ErroSemantico("uma tabela precisa ter pelo menos uma coluna")
        nomes = [c[0].casefold() for c in colunas]
        if len(nomes) != len(set(nomes)):
            raise ErroSemantico("nomes de coluna duplicados")
        objetos = tuple(Coluna(str(n), str(tipo).upper(), int(tam)) for n, tipo, tam in colunas)
        if sum(c.tamanho for c in objetos) > 4080:
            raise ErroSemantico("registro maior que o espaço disponível em uma página")
        tabela = Tabela(nome, objetos, pagina, 0)
        self.tabelas[chave] = tabela
        self.salva()
        return tabela

    def busca(self, nome: str) -> Tabela:
        try:
            return self.tabelas[nome.casefold()]
        except KeyError as exc:
            raise ErroSemantico(f"tabela {nome} não existe") from exc

    def atualiza_slots(self, nome: str, slots_usados: int):
        t = self.busca(nome)
        self.tabelas[nome.casefold()] = Tabela(t.nome, t.colunas, t.pagina, slots_usados)
        self.salva()

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
