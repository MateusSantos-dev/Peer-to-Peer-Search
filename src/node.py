# Python 3.5 or higher is required
import sys
import utils
import socket
import threading
from typing import Optional
from enum import Enum


class MessageType(Enum):
    HELLO = 1
    SEARCH = 2
    SEARCH_RANDOM_WALK = 3
    SEARCH_DEPTH_FIRST = 4
    STATISTICS = 5
    CHANGE_TTL = 6


class Node:
    def __init__(
            self,
            ip: str,
            port: int,
            neighbors: Optional[list[tuple[str, int]]],
            key_values: Optional[dict[str, int]]
    ) -> None:
        """Inicializa um novo nó da rede P2P."""

        # Se os parametros não forem passados, inicializa com valores padrão
        if neighbors is None:
            neighbors = []
        if key_values is None:
            key_values = {}

        self.ip = ip
        self.port = port
        self.sequence_number = 1  # numero de sequencia da mensagem
        self.socket = Node.create_socket(ip, port)
        self.data = key_values

        self.neighbors: dict[tuple[str, int], socket.socket] = self.connect_to_neighbors(neighbors)

    @staticmethod
    def create_socket(ip: str, port: int) -> socket.socket:
        """Cria um socket TCP IPv4 para o nó."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((ip, port))
        return sock

    def show_node(self) -> None:
        """Mostra as informações do nó."""
        print(f"IP: {self.ip}")
        print(f"Porta: {self.port}")
        self.show_neighbors()
        print("Chave_valor:")
        for key, value in self.data.items():
            print(f"    {key}: {value}")

    def show_neighbors(self) -> None:
        """Mostra os vizinhos do nó."""
        print(f"Há {len(self.neighbors)} vizinhos na tabela")
        for idx, (ip, port) in enumerate(self.neighbors.keys()):
            print(f"    [{idx}] {ip}:{port}")

    def receive_connections(self) -> None:
        """ Recebe conexões de outros nós e inicia uma thread para lidar com a conexão."""
        self.socket.listen()
        while True:
            connection, addr = self.socket.accept()
            threading.Thread(target=self.receive_message, args=(connection,), daemon=True).start()

    def receive_message(self, connection: socket.socket):
        """Recebe mensagens de um nó conectado."""
        try:
            while True:
                data = connection.recv(1024)
                if not data:
                    break
                self.interpret_message(data.decode())
        except ConnectionResetError:
            print("Connection reset")
        finally:
            connection.close()
            print(f"Connection closed")

    def interpret_message(self, message: str) -> None:
        """Interpreta uma mensagem recebida."""
        print(f'Mensagem recebida: "{message}"')
        parts = message.split(" ")
        origin = parts[0]
        seqno = parts[1]
        ttl = parts[2]
        operacao = parts[3]

        if operacao == MessageType.HELLO.name:
            ip, port = utils.convert_str_to_ip_port(origin)
            if (ip, port) in self.neighbors:
                print(f"Vizinho já está na tabela: {ip}:{port}")
            else:
                self.add_neighbor(ip, port)

    def connect_to_neighbors(self, neighbors: list[tuple[str, int]]):
        """Conecta-se aos vizinhos do nó."""
        all_neighbors = {}
        for neighbor in neighbors:
            ip, port = neighbor
            print(f"Tentando adicionar vizinho {ip}:{port}")
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((ip, port))
                self.send_hello(sock)
                all_neighbors[neighbor] = sock
                threading.Thread(target=self.receive_message, args=(sock,), daemon=True).start()
            except ConnectionRefusedError:
                print(f"Connection to {ip}:{port} refused")
        return all_neighbors

    def add_neighbor(self, ip: str, port: int) -> None:
        """Adiciona um vizinho ao nó."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ip, port))
        self.neighbors[(ip, port)] = sock
        print(f"    Adicionando vizinho na tabela: {ip}:{port}")

    def send_message(self, sock: socket.socket, message: str) -> None:
        """Envia uma mensagem para um nó."""
        ip, port = sock.getpeername()
        print(f'Encaminhando mensagem: "{message}" para {ip}:{port}')
        sock.sendall(message.encode())
        self.sequence_number += 1

    def send_hello(self, peer: socket.socket) -> None:
        """Envia uma mensagem HELLO para um vizinho."""
        message = self.craft_message(MessageType.HELLO, None)
        self.send_message(peer, message)

    def craft_message(self, message_type: MessageType, current_ttl: Optional[int]):
        """Cria uma mensagem para ser enviada."""
        origin = f"{self.ip}:{self.port}"
        seqno = self.sequence_number
        operacao = MessageType(message_type).name  # Converte o valor do Enum para o nome da operação
        if current_ttl is None:
            current_ttl = 100  # TTL padrão

        if message_type == MessageType.HELLO:
            current_ttl = 1
            return f"{origin} {seqno} {current_ttl} {operacao}"

    def pick_neighbor(self):
        """Retorna o vizinho escolhido pelo usuário"""
        self.show_neighbors()
        neighbor_idx = int(input("\n"))
        if neighbor_idx < 0 or neighbor_idx >= len(self.neighbors):
            print("Vizinho inválido")
            return None
        neighbor_chosen_key = list(self.neighbors.keys())[neighbor_idx]
        return self.neighbors[neighbor_chosen_key]


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


if __name__ == '__main__':
    node = create_node()
    node.show_node()
    threading.Thread(target=node.receive_connections, args=(), daemon=True).start()
    show_menu()
    opcao = input("digite o numero\n")
    node.send_hello(node.pick_neighbor())
    input("sair\n")
