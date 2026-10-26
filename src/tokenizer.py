"""Tokenizador SQL mínimo do JanusDB (M4)."""
from dataclasses import dataclass

PALAVRAS_RESERVADAS = {
    "CREATE", "TABLE", "INT", "CHAR", "INSERT", "INTO", "VALUES",
    "SELECT", "FROM", "WHERE",
}
SIMBOLOS = set("(),;*=")


class ErroLexico(ValueError):
    """Erro ao transformar texto SQL em tokens."""


@dataclass(frozen=True)
class Token:
    tipo: str
    valor: object
    posicao: int


def tokeniza(sql: str) -> list[Token]:
    if not isinstance(sql, str):
        raise TypeError("O comando SQL deve ser uma string")
    tokens: list[Token] = []
    i = 0
    while i < len(sql):
        c = sql[i]
        if c.isspace():
            i += 1
        elif c.isalpha() or c == "_":
            inicio = i
            i += 1
            while i < len(sql) and (sql[i].isalnum() or sql[i] == "_"):
                i += 1
            palavra = sql[inicio:i]
            if palavra.upper() in PALAVRAS_RESERVADAS:
                tokens.append(Token("PALAVRA", palavra.upper(), inicio))
            else:
                tokens.append(Token("NOME", palavra, inicio))
        elif c.isdigit():
            inicio = i
            while i < len(sql) and sql[i].isdigit():
                i += 1
            tokens.append(Token("NUMERO", int(sql[inicio:i]), inicio))
        elif c == "'":
            inicio = i
            i += 1
            partes = []
            while i < len(sql):
                if sql[i] == "'":
                    # Aspas duplicadas representam uma aspa literal: 'O''Brien'.
                    if i + 1 < len(sql) and sql[i + 1] == "'":
                        partes.append("'")
                        i += 2
                        continue
                    i += 1
                    break
                partes.append(sql[i])
                i += 1
            else:
                raise ErroLexico(f"aspas sem fechamento na posição {inicio}")
            tokens.append(Token("TEXTO", "".join(partes), inicio))
        elif c in SIMBOLOS:
            tokens.append(Token("SIMBOLO", c, i))
            i += 1
        else:
            raise ErroLexico(f"caractere inesperado {c!r} na posição {i}")
    tokens.append(Token("FIM", None, len(sql)))
    return tokens
