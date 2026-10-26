import pytest
from src.parser import analisa, ErroSintatico
from src.tokenizer import tokeniza, ErroLexico


def test_tokeniza_create():
    ts = tokeniza("CREATE TABLE aluno (id INT, nome CHAR(20));")
    assert ts[0].valor == "CREATE"
    assert ts[-1].tipo == "FIM"


def test_analisa_create_insert_select():
    assert analisa("CREATE TABLE aluno (id INT, nome CHAR(20));") == {
        "op": "CREATE", "tabela": "aluno", "colunas": [("id", "INT", 4), ("nome", "CHAR", 20)]
    }
    assert analisa("INSERT INTO aluno VALUES (7, 'Ana');") == {
        "op": "INSERT", "tabela": "aluno", "valores": [7, "Ana"]
    }
    assert analisa("SELECT nome FROM aluno WHERE id = 7") == {
        "op": "SELECT", "colunas": ["nome"], "tabela": "aluno", "where": ("id", 7)
    }


def test_erros_lexicos_e_sintaticos():
    with pytest.raises(ErroLexico):
        tokeniza("SELECT @ FROM aluno")
    with pytest.raises(ErroLexico):
        tokeniza("INSERT INTO t VALUES ('sem fim)")
    with pytest.raises(ErroSintatico):
        analisa("CREATE TABLE aluno (id INT nome CHAR(20))")
    with pytest.raises(ErroSintatico):
        analisa("SELECT * FROM aluno lixo")
