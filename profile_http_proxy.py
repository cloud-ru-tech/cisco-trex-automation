from trex.astf.api import *
import ipaddress
from dataclasses import dataclass

# запрос клиента делаем lambda, так как url на данный момент неизвестен
http_req = lambda url: f'GET /{url} HTTP/1.1\r\nHost: 10.10.0.17\r\nUser-Agent: Trex client emulator\r\nAccept: */*\r\n\r\n'
# заголовок и данные ответа сервера делаем lambda, так как content_length неизвестен
http_response_header = lambda content_length: f'HTTP/1.1 200 OK\r\nServer: Microsoft-IIS/6.0\r\nContent-Type: text/html\r\nContent-Length: {content_length}\r\n\r\n'
http_response_data = lambda data: f'<html><pre>{data}</pre></html>'

@dataclass
class ProfileConfig:
    client_ip_net: str # клиентская сеть в формате '10.127.0.0/16', в пакете из клиентского порта это будет IP src 
    lb_port: int       # порт балансировщика, например 80
    lb_ip_net: str     # сеть балансировщиков в формате '192.168.3.17/32', в пакете из клиентского порта это будет IP dst
    backend_port: int  # порт бэкэнд серверов. например 80
    backend_ip_net: str  # сеть бэкэнд серверов в формате '10.128.1.0/24', серверный порт будет обрабатывать только пакеты с задаными dst
    requests: int      # количество запросов в одной tcp сессии, например 200
    expected_payload_size: int # если test_url указан то это поле должно указывать размер страницы в байтах, которое будет присылать сервер. Если test_url не указан, то это поле указывает размер ответа которое будет генерировать trex бэкэнд.
    test_url: str |  None = None      # используется только с настоящими backend серверами, например 'index.html'

def get_net_range(net: str):
    # находим начальный IP и конечный IP в указаных сетях. это нужно trex библиотекам, которые работают в таком формате
    net = ipaddress.IPv4Network(net)
    net_ip_list = list(net.hosts())
    return [str(net_ip_list[0]),  str(net_ip_list[-1])]
        

class lb_Profile():
    def __init__(self):
        pass

    # функция генерации ответа заданной длины
    # response_size - это длина данных tcp пакета включая http заголовок
    def construct_response(self, response_size):
        # длина минимального ответа это сумма длины заголовка и данных
        header_len = len(http_response_header("") + http_response_data("")) 
        # если запрашиваемый размер меньше заголовка то возвращаем минимально возможный ответ
        if response_size <= header_len:
            
            resp_data = http_response_data('')
        else:
            data_len = response_size - header_len
            padding = '*' * data_len
            resp_data = http_response_data(padding)
        resp_header = http_response_header(len(resp_data))
        response = resp_header + resp_data
        return response, len(response)

    # стандартная функция, которая вызывается библиотекой trex. Она должна вернуть профиль трафика
    def get_profile(self, tunables, **kwargs):
        config = ProfileConfig(**kwargs)

        # описание одной tcp сессии клиента
        prog_c = ASTFProgram()
        # если указан test_url то это значит что мы работаем с настоящим backend сервером
        if config.test_url:
            url = config.test_url
            expected_size = config.expected_payload_size
            # просто инициализируем переменую так как она используется далее
            response = "no value"
        else:  # генерируем ответ бэкэнд сервера
            url = "index.html"
            response, expected_size = self.construct_response(config.expected_payload_size)
        # поле request хранит количество send/receive итераций для одной tcp сессии
        for req in range(config.requests):
            # отсылаем запрос
            prog_c.send(http_req(url))
            # так как это не настоящий клиент, единственное что он валидирует это размер полученного ответа
            # получаем ответ и валидируем его
            prog_c.recv(expected_size)

        # описание одной tcp сессии бэкэнда
        prog_s = ASTFProgram()
        for req in range(config.requests):
            prog_s.recv(len(http_req(url)))
            prog_s.delay(10)
            prog_s.send(response)

        # описываем какие ip адреса генерировать для клиентов.
        # src клиентов
        ip_gen_c = ASTFIPGenDist(ip_range=get_net_range(config.client_ip_net), distribution="seq")
        # dst клиентов
        ip_gen_s = ASTFIPGenDist(ip_range=get_net_range(config.lb_ip_net), distribution="seq")

        # создаем генератор ip адресов для клиентского порта
        ip_gen = ASTFIPGen(glob=ASTFIPGenGlobal(ip_offset="1.0.0.0"),
                           dist_client=ip_gen_c,
                           dist_server=ip_gen_s)
        info = ASTFGlobalInfoPerTemplate()
        info.tcp.mss = 1560
        info.tcp.initwnd = 1
        info.tcp.no_delay = 3
        temp_c = ASTFTCPClientTemplate(program=prog_c, glob_info=info, ip_gen=ip_gen, port=config.lb_port)

        # для серверной части ip адреса генерировать не надо. Надо просто указать на какой входящий трафик надо отвечать, для этого создаем ассоциацию
        backend_range = get_net_range(config.backend_ip_net)
        temp_s = ASTFTCPServerTemplate(program=prog_s,
                                       glob_info=info,
                                       assoc=ASTFAssociationRule(port=config.backend_port,
                                                                 ip_start=backend_range[0],
                                                                 ip_end=backend_range[1]))
        # объединяем клиентский и серверный шаблоны
        template = ASTFTemplate(client_template=temp_c, server_template=temp_s)

        # создаем и возвращаем профиль трафика
        profile = ASTFProfile(default_ip_gen=ip_gen, templates=template)
        return profile


def register():
    return lb_Profile()


