import pytest
from src.operadores import Operador
from src.sort import CodecLinha, Sort


class OperadorLista(Operador):
    """Operador simples para alimentar testes a partir de uma lista em memória."""

    def __init__(self, linhas):
        self.linhas = list(linhas)
        self.pos = 0
        self.aberto = False

    def abre(self):
        self.pos = 0
        self.aberto = True

    def proximo(self):
        if not self.aberto or self.pos >= len(self.linhas):
            return None
        linha = self.linhas[self.pos]
        self.pos += 1
        return linha

    def fecha(self):
        self.aberto = False


def test_codec_linha_codifica_e_decodifica():
    esquema = [("id", "INT", 4), ("nome", "CHAR", 10), ("total", "BIGINT", 8)]
    codec = CodecLinha(esquema)
    assert codec.tamanho_registro == 22

    linha = (42, "Janus", 9876543210)
    bytes_codificados = codec.codifica(linha)
    assert len(bytes_codificados) == 22

    recuperado = codec.decodifica(bytes_codificados)
    assert recuperado == (42, "Janus", 9876543210)


def test_codec_linha_validacoes():
    codec = CodecLinha([("id", "INT", 4), ("sigla", "CHAR", 3)])
    with pytest.raises(ValueError):
        codec.codifica((1,))  # Poucos valores
    with pytest.raises(ValueError):
        codec.codifica((1, "MUITOLONGO"))  # Excede CHAR(3)
    with pytest.raises(ValueError):
        codec.decodifica(b"\x00" * 3)  # Menos bytes que o tamanho_registro


def test_sort_em_memoria_asc_e_desc():
    dados = [(3, "Carlos"), (1, "Ana"), (2, "Bruno")]
    fonte = OperadorLista(dados)

    # Teste ASC por id (coluna 0)
    sort_asc = Sort(fonte, coluna_idx=0, direcao="ASC")
    with sort_asc:
        res_asc = list(sort_asc)
    assert res_asc == [(1, "Ana"), (2, "Bruno"), (3, "Carlos")]

    # Teste DESC por id (coluna 0)
    sort_desc = Sort(fonte, coluna_idx=0, direcao="DESC")
    with sort_desc:
        res_desc = list(sort_desc)
    assert res_desc == [(3, "Carlos"), (2, "Bruno"), (1, "Ana")]

    # Teste ASC por nome (coluna 1)
    sort_nome_asc = Sort(fonte, coluna_idx=1, direcao="ASC")
    with sort_nome_asc:
        assert list(sort_nome_asc) == [(1, "Ana"), (2, "Bruno"), (3, "Carlos")]

    # Teste DESC por nome (coluna 1)
    sort_nome_desc = Sort(fonte, coluna_idx=1, direcao="DESC")
    with sort_nome_desc:
        assert list(sort_nome_desc) == [(3, "Carlos"), (2, "Bruno"), (1, "Ana")]


def test_sort_estabilidade():
    # Chaves repetidas devem preservar a ordem relativa original
    dados = [(1, "Primeiro"), (2, "Outro"), (1, "Segundo"), (1, "Terceiro")]
    fonte = OperadorLista(dados)

    sort_estavel = Sort(fonte, coluna_idx=0, direcao="ASC")
    with sort_estavel:
        res = list(sort_estavel)

    assert res == [(1, "Primeiro"), (1, "Segundo"), (1, "Terceiro"), (2, "Outro")]


def test_sort_casos_borda():
    # Entrada vazia
    sort_vazio = Sort(OperadorLista([]), coluna_idx=0)
    with sort_vazio:
        assert list(sort_vazio) == []

    # Entrada de um único item
    sort_um = Sort(OperadorLista([(10, "X")]), coluna_idx=0)
    with sort_um:
        assert list(sort_um) == [(10, "X")]

    # mem_paginas menor que 3 é rejeitado
    with pytest.raises(ValueError):
        Sort(OperadorLista([]), coluna_idx=0, mem_paginas=2)

    # Direção inválida
    with pytest.raises(ValueError):
        Sort(OperadorLista([]), coluna_idx=0, direcao="INVALIDO")
