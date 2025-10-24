#!/bin/python

import astf_path
from trex.astf.api import *

from pprint import pprint
import argparse
#import os
from pathlib import PurePath
import sys
import time

def astf_test(server, profile_path, args):

    # создаем клиента, в качестве аргумента IP адрес машины где запущен trex
    c = ASTFClient(server=server)
    c.connect()
    c.acquire(force=True)
    passed = True

    try:
        c.reset()

        # подготавилвает путь к профилю и его аргументы
        if not profile_path:
            profile_path = str(PurePath(astf_path.get_profiles_path(), profile_path))
        profile_keys = []
        original_dict = vars(args)
        # из всех аргументов теста фильтруем аргументы профиля
        profile_keys = {'client_ip_net', 
                        'lb_ip_net',
                        'lb_port',
                        'backend_ip_net',
                        'backend_port',
                        'requests', 
                        'expected_payload_size',
                        'test_url'}
        profile_args = {k: original_dict[k] for k in profile_keys}

        print("Запускаем трафик с множителем '%s' на %s секунд" % (args.bottom_multi, args.duration))
        have_drops = False
        print("<h4>{}  запросов на соединение. Размер ответа: {} байт </h4>".format(args.requests, args.expected_payload_size))
        print('<table><tbody><tr><th scope="col">Active clients</th><th scope="col">KPPS</th><th scope="col">CPS</th><th scope="col">Bandwidth(MB) </th><th  scope="col">Drop rate</th></tr>')
        for multi in range(args.bottom_multi, args.top_multi, args.step_multi):
            c.load_profile(profile_path, tunables=profile_args)
            # сбрасываем статистику вначале каждой иттерации
            c.clear_stats()

            # c.start(mult=multi, duration=duration, client_mask=1) # если нужно выключить серверный порт
            c.start(mult=multi, duration=args.duration)
            time.sleep(args.duration - 5)
            stat = c.get_stats()
            gstats = stat['global']
            # генерируем html отчет
            td = lambda data: f"<td>{data}</td>"
            tr = lambda data: f"<tr>{data}</tr>"
            print(tr("".join(map(td, [multi,                       # Active clients
                     (gstats['rx_pps'] + gstats['tx_pps']) / 1000, # KPPS
                     gstats['tx_cps'],                             # CPS
                     (gstats['rx_bps']+gstats['tx_bps'])/(1024*1024), # Bandwidth(MB)
                     gstats['rx_drop_bps']]))))                     # Drop rate
            if gstats['rx_drop_bps'] > 0:
                have_drops = True
                break
            c.stop()
            c.wait_on_traffic(timeout=60)
            c.reset()
            if args.pause:
                time.sleep(args.pause)


        print('</tbody></table>')
        if c.get_warnings():
            print('\n\n*** test had warnings ****-{}\n\n'.format(c.get_warnings()))
            for w in c.get_warnings():
                print(w)
            print("TEST FAILED")
        elif have_drops:
            print("TEST FAILED")
        else:
            print("TEST PASSED")


    finally:
        c.disconnect()
    return 0

def parse_args():
    parser = argparse.ArgumentParser(description='Тест производительности для прокси балансировщика. Тест запускает несколько итераций тестирования. Каждая итерация длится -d секунд. Каждая итерация создает bottom-multi + шаг * step_multi соединений в секунду. Таким образом можно найти на каком количестве соединений балансировщик начинает сбоить')
    parser.add_argument('-s',
                        dest='server',
                        help='адрес TRex генератора',
                        default='127.0.0.1',
                        type=str)
    parser.add_argument('--client-ip-net',
                        help="Клиентская IP сеть в формате '16.0.0.0/8'",
                        default='16.0.0.0/8',
                        type=str)
    parser.add_argument('--lb-ip-net',
                        help="Адрес IP сети балансировщика",
                        required=True,
                        type=str)
    parser.add_argument('--lb-port',
                        help="TCP порт балансировщика",
                        required=True,
                        type=int)
    parser.add_argument('--backend-ip-net',
                        help="IP сеть бэкэнд серверов в формате '48.0.0.0/8'",
                        default='48.0.0.0/8',
                        type=str)
    parser.add_argument('--backend-port',
                        help="TCP порт бэкэнд серверов",
                        required=True,
                        type=int)
    parser.add_argument('--top-multi',
                        help='Верхняя граница множителя. Множитель управляет количеством новых TCP соединений в секунду',
                        default=100,
                        type=int)
    parser.add_argument('--bottom-multi',
                        help='Нижняя граница множителя. Множитель управляет количеством новых TCP соединений в секунду',
                        default=100,
                        type=int)
    parser.add_argument('--step-multi',
                        help='Шаг с которым перебираются множители от нижней границе к верхней. Каждая итерация продолжается -d cекунд. См. -d аргумент',
                        default=100,
                        type=int)
    parser.add_argument('-f',
                        dest='profile',
                        help='путь к профилю.',
                        default='profile_http_proxy.py',
                        type=str)
    parser.add_argument('-d',
                        default=15,
                        dest='duration',
                        help='длина итерации в секундах',
                        type=float)
    parser.add_argument('-p',
                        dest='pause',
                        help='Длина паузы между итерациями. Значение по умолчанию 0 сек. Если тест проходит с живыми бэкэнд серверами то рекомендуется этот аргумент выставить в 120 сек.',
                        type=float)
    parser.add_argument('-n',
                        default=200,
                        dest='requests',
                        help='Количество запросов, которые будет генерировать клиент к серверу в одном TCP соединение.',
                        type=int)
    parser.add_argument('--test-url',
                        help="URL для запросов. Указывать только если трафик генерируеться к настоящему web серверу",
                        type=str)
    parser.add_argument('--expected-payload-size',
                        help="Ожидаемый размер данных в пакете. Если test-url указанно то этот аргумент должен указывать размер страницы которая будет возвращаться от сервера. Если test-url не указан, тогда этот агрумент будет генерировать необходимый размер от сервера и валидировать его.",
                        default=128,
                        type=int)

    return parser.parse_args()


def main():
    args = parse_args()

    return astf_test(args.server, args.profile, args)

if __name__ == "__main__":
    main()


