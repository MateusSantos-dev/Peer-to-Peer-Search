import sys
import utils
import asyncio
from typing import Optional


class Node:
    def __init__(
            self,
            ip: str,
            port: int,
            neighbors: Optional[list[tuple[str, int]]],
            data: Optional[dict[str, int]]
    ) -> None:
        """Inicializa um novo nó da rede P2P."""

        # Se os parametros não forem passados, inicializa com valores padrão
        if neighbors is None:
            neighbors = []
        if data is None:
            data = {}

        self.ip = ip
        self.port = port
        self.neighbors = neighbors
        self.data = data

    async def show_node(self) -> None:
        """Mostra as informações do nó."""
        print(f"IP: {self.ip}")
        print(f"Porta: {self.port}")
        await self.show_neighbors()
        print("Chave_valor:")
        for key, value in self.data.items():
            print(f"    {key}: {value}")

    async def show_neighbors(self) -> None:
        """Mostra os vizinhos do nó."""
        print(f"Há {len(self.neighbors)} vizinhos na tabela")
        for idx, neighbor in enumerate(self.neighbors):
            print(f"    [{idx}] {neighbor[0]} {neighbor[1]}")


def create_node() -> Node:
    """Cria um novo nó da rede P2P usando os argumentos passados na inicialização do programa."""

    # Se não houver argumentos suficientes, exibe uma mensagem de erro e encerra o programa
    if len(sys.argv) < 2:  # sys.argv[0] é o nome do arquivo
        raise SystemExit(f"Esperado 1 argumento, recebido 0")

    neighbors = None
    data = None

    ip, port = utils.convert_str_to_ip_port(sys.argv[1])

    if not utils.is_valid_ip(ip) or not utils.is_valid_port(port):
        raise ValueError(f"IP ou porta inválidos {ip}:{port}")

    if len(sys.argv) >= 3:
        neighbors = utils.get_all_neighbors_from_file(sys.argv[2])

    if len(sys.argv) >= 4:
        data = utils.get_key_value_from_file(sys.argv[3])

    return Node(ip, port, neighbors, data)


def show_menu() -> None:
    """Mostra o menu de comandos disponiveis para o usuario."""
    print("""
Escolha o comando
    [0] Listar vizinhos
    [1] HELLO
    [2] SEARCH (flooding)
    [3] SEARCH (random walk)
    [4] SEARCH (busca em profundidade)
    [5] Estatisticas
    [6] Alterar valor padrao de TTL
    [9] Sair
""")


async def main() -> None:
    node = create_node()
    await node.show_node()
    show_menu()

if __name__ == '__main__':
    asyncio.run(main())
