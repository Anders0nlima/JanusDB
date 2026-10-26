"""Parser SQL por descida recursiva para o subconjunto do M4."""
from .tokenizer import Token, tokeniza


class ErroSintatico(ValueError):
    """O comando não respeita a gramática SQL implementada."""


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.i = 0

    def olha(self) -> Token:
        return self.tokens[self.i]

    def aceita(self, tipo: str, valor=None) -> bool:
        t = self.olha()
        if t.tipo == tipo and (valor is None or t.valor == valor):
            self.i += 1
            return True
        return False

    def espera(self, tipo: str, valor=None):
        t = self.olha()
        if t.tipo != tipo or (valor is not None and t.valor != valor):
            esperado = valor if valor is not None else tipo
            raise ErroSintatico(f"esperava {esperado}, veio {t.valor!r} na posição {t.posicao}")
        self.i += 1
        return t.valor

    def nome(self) -> str:
        return self.espera("NOME")

    def valor(self):
        t = self.olha()
        if t.tipo in ("NUMERO", "TEXTO"):
            self.i += 1
            return t.valor
        raise ErroSintatico(f"esperava valor (número ou texto), veio {t.valor!r} na posição {t.posicao}")

    def coluna(self):
        nome = self.nome()
        if self.aceita("PALAVRA", "INT"):
            return (nome, "INT", 4)
        self.espera("PALAVRA", "CHAR")
        self.espera("SIMBOLO", "(")
        tamanho = self.espera("NUMERO")
        if tamanho <= 0:
            raise ErroSintatico("o tamanho de CHAR deve ser maior que zero")
        self.espera("SIMBOLO", ")")
        return (nome, "CHAR", tamanho)

    def create(self):
        self.espera("PALAVRA", "CREATE")
        self.espera("PALAVRA", "TABLE")
        tabela = self.nome()
        self.espera("SIMBOLO", "(")
        colunas = [self.coluna()]
        while self.aceita("SIMBOLO", ","):
            colunas.append(self.coluna())
        self.espera("SIMBOLO", ")")
        return {"op": "CREATE", "tabela": tabela, "colunas": colunas}

    def insert(self):
        self.espera("PALAVRA", "INSERT")
        self.espera("PALAVRA", "INTO")
        tabela = self.nome()
        self.espera("PALAVRA", "VALUES")
        self.espera("SIMBOLO", "(")
        valores = [self.valor()]
        while self.aceita("SIMBOLO", ","):
            valores.append(self.valor())
        self.espera("SIMBOLO", ")")
        return {"op": "INSERT", "tabela": tabela, "valores": valores}

    def select(self):
        self.espera("PALAVRA", "SELECT")
        if self.aceita("SIMBOLO", "*"):
            colunas = ["*"]
        else:
            colunas = [self.nome()]
            while self.aceita("SIMBOLO", ","):
                colunas.append(self.nome())
        self.espera("PALAVRA", "FROM")
        tabela = self.nome()
        where = None
        if self.aceita("PALAVRA", "WHERE"):
            coluna = self.nome()
            self.espera("SIMBOLO", "=")
            where = (coluna, self.valor())
        return {"op": "SELECT", "colunas": colunas, "tabela": tabela, "where": where}

    def comando(self):
        t = self.olha()
        if t.tipo != "PALAVRA":
            raise ErroSintatico(f"comando desconhecido {t.valor!r} na posição {t.posicao}")
        if t.valor == "CREATE":
            arvore = self.create()
        elif t.valor == "INSERT":
            arvore = self.insert()
        elif t.valor == "SELECT":
            arvore = self.select()
        else:
            raise ErroSintatico(f"comando desconhecido {t.valor!r} na posição {t.posicao}")
        self.aceita("SIMBOLO", ";")
        self.espera("FIM")
        return arvore


def analisa(sql: str) -> dict:
    """Tokeniza e analisa um único comando SQL, devolvendo sua árvore sintática."""
    return Parser(tokeniza(sql)).comando()
