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


def test_analisa_group_by_order_by_count_sum():
    assert analisa("SELECT COUNT(*), SUM(salario) FROM funcionario") == {
        "op": "SELECT",
        "colunas": [("COUNT", "*"), ("SUM", "salario")],
        "tabela": "funcionario",
        "where": None,
    }
    assert analisa("SELECT depto, COUNT(*) FROM funcionario GROUP BY depto") == {
        "op": "SELECT",
        "colunas": ["depto", ("COUNT", "*")],
        "tabela": "funcionario",
        "where": None,
        "group_by": "depto",
    }
    assert analisa("SELECT id, nome FROM aluno ORDER BY nome DESC") == {
        "op": "SELECT",
        "colunas": ["id", "nome"],
        "tabela": "aluno",
        "where": None,
        "order_by": ("nome", "DESC"),
    }
    assert analisa("SELECT id FROM aluno ORDER BY id") == {
        "op": "SELECT",
        "colunas": ["id"],
        "tabela": "aluno",
        "where": None,
        "order_by": ("id", "ASC"),
    }


def test_erros_sintaticos_novas_clausulas():
    with pytest.raises(ErroSintatico):
        analisa("SELECT * FROM aluno ORDER id")  # ORDER sem BY
    with pytest.raises(ErroSintatico):
        analisa("SELECT SUM(*) FROM aluno")  # SUM requer nome de coluna, não *
    with pytest.raises(ErroSintatico):
        analisa("SELECT COUNT(id) FROM aluno")  # COUNT só aceita *
    with pytest.raises(ErroSintatico):
        analisa("SELECT * FROM aluno GROUP depto")  # GROUP sem BY

