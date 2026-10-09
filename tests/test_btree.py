import os
import random

from src.btree import BPlusTree
from src.cache import PageCache
from src.storage import Pager

ARQUIVO_TESTE = "data/teste_btree.db"


def setup_function():
    os.makedirs("data", exist_ok=True)
    if os.path.exists(ARQUIVO_TESTE):
        try:
            os.remove(ARQUIVO_TESTE)
        except PermissionError:
            pass


def test_busca_em_no_folha_unico():
    """Testa inserções simples em uma folha única sem divisão."""
    pager = Pager(ARQUIVO_TESTE)
    cache = PageCache(pager, capacidade=4)
    try:
        tree = BPlusTree(cache)

        assert tree.search(10) is None

        tree.insert(10, 100)
        tree.insert(5, 50)
        tree.insert(20, 200)

        assert tree.search(10) == 100
        assert tree.search(5) == 50
        assert tree.search(20) == 200
        assert tree.search(99) is None

        # Atualização de valor para chave existente
        tree.insert(10, 999)
        assert tree.search(10) == 999
    finally:
        cache.close()


def test_primeiro_split_de_folha():
    """Testa a divisão da folha raiz e a criação do primeiro nó interno pai."""
    pager = Pager(ARQUIVO_TESTE)
    cache = PageCache(pager, capacidade=5)
    try:
        # Com max_leaf_keys=3, a 4ª inserção deve disparar um split
        tree = BPlusTree(cache, max_leaf_keys=3, max_internal_keys=3)

        tree.insert(1, 10)
        tree.insert(2, 20)
        tree.insert(3, 30)

        assert tree.root_page_id == 0

        # 4ª inserção: dispara split da folha!
        tree.insert(4, 40)

        # A nova raiz deve ser um novo nó interno criado
        assert tree.root_page_id != 0

        # Todas as chaves devem continuar acessíveis
        assert tree.search(1) == 10
        assert tree.search(2) == 20
        assert tree.search(3) == 30
        assert tree.search(4) == 40

        # A lista encadeada horizontal deve estar correta
        assert tree.items() == [(1, 10), (2, 20), (3, 30), (4, 40)]
    finally:
        cache.close()


def test_multiplos_splits_e_splits_internos():
    """Testa árvore com múltiplos níveis de nós internos e splits em cascata."""
    pager = Pager(ARQUIVO_TESTE)
    cache = PageCache(pager, capacidade=10)
    try:
        # Nós bem pequenos para forçar splits frequentes
        tree = BPlusTree(cache, max_leaf_keys=3, max_internal_keys=3)

        # Insere 40 elementos sequenciais
        for i in range(1, 41):
            tree.insert(i, i * 100)

        # Verifica se todas as chaves são encontradas
        for i in range(1, 41):
            assert tree.search(i) == i * 100, f"Falha na busca pela chave {i}"

        assert tree.search(0) is None
        assert tree.search(41) is None

        # Itens ordenados de ponta a ponta
        itens = tree.items()
        assert len(itens) == 40
        assert itens == [(i, i * 100) for i in range(1, 41)]
    finally:
        cache.close()


def test_range_search():
    """Testa varredura horizontal por intervalo [inicio, fim]."""
    pager = Pager(ARQUIVO_TESTE)
    cache = PageCache(pager, capacidade=8)
    try:
        tree = BPlusTree(cache, max_leaf_keys=3, max_internal_keys=3)

        for i in range(1, 21):
            tree.insert(i, i * 10)

        # Intervalo no meio da árvore
        resultado = tree.range_search(5, 12)
        esperado = [(i, i * 10) for i in range(5, 13)]
        assert resultado == esperado

        # Intervalo com chave inexistente nos extremos
        resultado2 = tree.range_search(0, 3)
        esperado2 = [(1, 10), (2, 20), (3, 30)]
        assert resultado2 == esperado2

        # Intervalo vazio
        assert tree.range_search(50, 60) == []
        assert tree.range_search(10, 5) == []
    finally:
        cache.close()


def test_persistencia_apos_fechar_e_reabrir():
    """Garante que a Árvore B+ sobrevive ao fechamento e reabertura do arquivo."""
    pager = Pager(ARQUIVO_TESTE)
    cache = PageCache(pager, capacidade=5)
    try:
        tree = BPlusTree(cache, max_leaf_keys=3, max_internal_keys=3)

        for i in range(1, 16):
            tree.insert(i, i * 7)

        raiz_salva = tree.root_page_id
    finally:
        cache.close()

    # Reabre com novas instâncias de Pager e PageCache
    pager_reaberto = Pager(ARQUIVO_TESTE)
    cache_reaberto = PageCache(pager_reaberto, capacidade=5)
    try:
        tree_reaberta = BPlusTree(
            cache_reaberto,
            root_page_id=raiz_salva,
            max_leaf_keys=3,
            max_internal_keys=3,
        )

        for i in range(1, 16):
            assert tree_reaberta.search(i) == i * 7

        assert tree_reaberta.items() == [(i, i * 7) for i in range(1, 16)]
    finally:
        cache_reaberto.close()


def test_insercoes_aleatorias():
    """Testa integridade com chaves inseridas fora de ordem."""
    pager = Pager(ARQUIVO_TESTE)
    cache = PageCache(pager, capacidade=10)
    try:
        tree = BPlusTree(cache, max_leaf_keys=4, max_internal_keys=4)

        numeros = list(range(1, 51))
        random.seed(42)
        random.shuffle(numeros)

        esperado = {}
        for n in numeros:
            valor = n * 3
            tree.insert(n, valor)
            esperado[n] = valor

        for n in numeros:
            assert tree.search(n) == esperado[n]

        # Verifica se os itens saem ordenados
        chaves_ordenadas = sorted(esperado.keys())
        assert tree.items() == [(k, esperado[k]) for k in chaves_ordenadas]
    finally:
        cache.close()


def test_validacao_de_parametros():
    """Garante validação para chaves e valores inválidos."""
    pager = Pager(ARQUIVO_TESTE)
    cache = PageCache(pager)
    try:
        tree = BPlusTree(cache)

        try:
            tree.insert(-1, 10)
            assert False, "Deveria rejeitar chave negativa"
        except ValueError:
            pass

        try:
            tree.insert(True, 10)  # bool herda de int
            assert False, "Deveria rejeitar booleano"
        except ValueError:
            pass

        try:
            tree.search("10")  # type: ignore
            assert False, "Deveria rejeitar string"
        except ValueError:
            pass
    finally:
        cache.close()

