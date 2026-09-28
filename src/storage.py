import os
import struct

PAGE_SIZE = 4096 
HEADER_SIZE = 16 
RECORD_SIZE = 8

class Pager:
    """
    um objeto que guarda o arquivo aberto e o número de páginas.
    """
    def __init__(self, caminho):
        novo = not os.path.exists(caminho)
        self.f = open(caminho, "w+b" if novo else "r+b")
        self.f.seek(0, os.SEEK_END)
        self.n_paginas = self.f.tell() // PAGE_SIZE

    def _valida(self, n):
        if n < 0:
            raise ValueError(f"Página inválida: {n}")

    def le(self, n):
        self._valida(n)
        self.f.seek(n * PAGE_SIZE)
        buf = self.f.read(PAGE_SIZE)
        if len(buf) != PAGE_SIZE:
            raise IOError(f"página {n} truncada: {len(buf)} bytes")
        return bytearray(buf)

    def escreve(self, n, buf):
        self._valida(n)
        if len(buf) != PAGE_SIZE:
            raise ValueError(f"página com {len(buf)} bytes")
        self.f.seek(n * PAGE_SIZE)
        self.f.write(buf)

    def aloca(self):
        """cria uma página nova em branco e devolve o número dela."""
        n = self.n_paginas
        self.f.seek(n * PAGE_SIZE)
        self.f.write(bytes(PAGE_SIZE)) # 4096 zeros
        self.n_paginas += 1
        return n

    def sync(self):
        """garante que os dados sobrevivam a um 'kill -9' forçando a gravação no disco físico."""
        self.f.flush()
        os.fsync(self.f.fileno())

    def fecha(self):
        self.sync()
        self.f.close()


def calcula_deslocamento(pagina: int, slot: int) -> int:
    """calcula em qual byte absoluto do arquivo começa um registro."""
    return (pagina * PAGE_SIZE) + HEADER_SIZE + (slot * RECORD_SIZE)


def serializa_registro(id_aluno: int, matricula: int) -> bytes:
    """converte os dados do aluno para 8 bytes."""
    return struct.pack('<II', id_aluno, matricula)


def desserializa_registro(dados: bytes) -> tuple[int, int]:
    """le os 8 bytes e converte de volta para (id_aluno, matricula)."""
    if len(dados) != RECORD_SIZE:
        raise ValueError(f"Registro deve ter {RECORD_SIZE} bytes.")
    return struct.unpack('<II', dados)
