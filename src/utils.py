def is_valid_ip(ip: str) -> bool:
    """Verifica se um IP é válido."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if int(part) < 0 or int(part) > 255:
            return False
    return True


def is_valid_port(port: int) -> bool:
    """Verifica se uma porta é válida."""
    return 1 <= port <= 65535


def get_lines_from_file(file_path: str) -> list[str]:
    """Retorna as linhas de um arquivo."""
    with open(file_path, "r") as file:
        return file.read().splitlines()


def convert_str_to_ip_port(address: str) -> tuple[str, int]:
    """Converte uma string para um par (ip, porta)."""
    try:
        ip, port = address.split(":")
        return ip, int(port)
    except ValueError:
        raise ValueError(f"Argumento não segue o formato ip:porta: {address}")


def get_key_value_from_file(file_path: str) -> dict[str, str]:
    """Retorna um dicionario de chave-valor a partir de um arquivo."""
    lines = get_lines_from_file(file_path)
    data = {}
    for line in lines:
        key, value = line.split(" ")
        data[key] = value
    return data


def get_all_neighbors_from_file(file_path: str) -> list[tuple[str, int]]:
    """Retorna uma lista de tuplas (ip, porta) a partir de um arquivo."""
    lines = get_lines_from_file(file_path)
    neighbors = []
    for line in lines:
        ip, port = convert_str_to_ip_port(line)

        if not is_valid_ip(ip) or not is_valid_port(port):
            raise ValueError(f"IP ou porta inválidos {ip}:{port}")

        neighbors.append((ip, port))
    return neighbors
