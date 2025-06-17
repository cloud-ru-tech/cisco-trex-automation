# cisco trex automation 

## Установка
```
wget https://trex-tgn.cisco.com/trex/release/v3.06.tar.gz --no-check-certificate
sudo tar -C /opt -xzf v3.06.tar.gz
sudo mv /opt/{,trex_}v3.06
```

## Запуск trex. 
Теперь настроим enp2s0 как порт клиентской сети и enp3s0 как порт серверной сети
Убедитесь, что интерфейсы находятся в состоянии UP:
```
sudo ip link set enp2s0 up
sudo ip link set enp3s0 up
```

Тут стоит отметить, что trex может работать как с помощью dpdk библиотеки, так и с обычными линуксовыми портами. Производительность с линуксовыми портами конечно, ниже но так как мы собираемся тестировать L7 сервис, то нам этой производительности должно хватить. Создаем конфигурационный файл:
 ```
sudo -i 
cat <<EOF>/etc/trex_cfg.yaml
- version       : 2 # version 2 of the configuration file
  low_end       : true
  interfaces    : ["enp2s0","enp3s0"]   # если нужен только пользовательский трафик, а бэки у вас будут настоящие, можете в качестве второго интерфейса указать “dummy”
  port_limit      : 2
  port_info: 
    - ip    : 192.168.1.2    # адрес клиентского порта на виртуальной машине 
      default_gw : 192.168.1.1 # адрес клиентского порта на дефолтном маршрутизаторе
    - ip    : 192.168.1.6  # адрес серверного порта на виртуальной машине
      default_gw : 192.168.1.5 # адрес серверного порта на маршрутизаторе
EOF
```

Для успешного запуска trex потребуется выделить ему hugepages.
```
echo 2048 > /proc/sys/vm/nr_hugepages
```

### Запуск trex в statefull режиме для Ubuntu 22.04
```
cd /opt/trex_v3.06/
./_t-rex-64 -i --astf
```

### Запуск trex в statefull режиме для Ubuntu 24.04
```
cd /opt/trex_v3.06/

./_t-rex-64 -i --astf

# выдает ошибку:
./_t-rex-64: so/x86_64/libstdc++.so.6: version `GLIBCXX_3.4.30' not found (required by /lib/x86_64-linux-gnu/libicuuc.so.74)
# чтобы победить эту ошибку, нужно удалить файл libstdc++.so.6 в папке trex
rm so/x86_64/libstdc++.so.6
# и поставить python3.11
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update && sudo apt install python3.11 python3.11-venv
cd v3.06   # wherever you untarred trex 3.06
python3.11 -m venv venv
source ./venv/bin/activate
venv/bin/python venv/bin/pip install cffi

./_t-rex-64 -i --astf
```
trex готов к работе. Теперь чтобы воспользоваться генератором, нужно подключится к нему с помощью клиента. Можно запускать trex как локально, так и с удаленной машины. Доступно два варианта:
* trex_client_v3.06.tar.gz - python клиент
* trex-console - консольный терминал


## Запуск тестов

Для запуска скриптов необходим Python-клиент. Он входит в состав trex в виде архива trex_client_v3.06.tar.gz. Клиента можно запускать как удаленно, так и локально. Мы распакуем его локально
```
$ tar -C ~/ -xvf trex_client_v3.06.tar.gz
```
Копируем наши тесты в папку с тестами:
```
$ cp profile_http_proxy.py test_proxy.py ~/trex_client/interactive/trex/examples/astf/
```
Переходим в папку с тестами
```
$ cd ~/trex_client/interactive/trex/examples/astf/
```
Eсли окружение Ubuntu 24.04, то активируем окружение python3.11
```
source /opt/trex_v3.06/venv/bin/activate
```

Запускаем тест с 1000 паралельных клиентов, каждые 15 секунд увеличиваем количество клиентов на 1000 и так до 20K пользователей. Размер ответа сервера -- 128 байт
```
$ python3 test_proxy.py --backend-port 80 --backend-ip-net 10.10.0.17/32 --lb-ip-net 10.10.0.17/32 --lb-port 80 --client-ip-net 10.10.1.0/24 --bottom-multi 1000 --top-multi 20000 --step-multi 1000 -d 15 -p 15 -n 1 --test-url 128.html --expected-payload-size 128
```
Запускаем тест с 1000 паралельных клиентов, каждые 15 секунд увеличиваем количество клиентов на 1000 и так до 20K пользователей. Размер ответа сервера -- 752 байта
```
$ python3 test_proxy.py --backend-port 80 --backend-ip-net 10.10.0.17/32 --lb-ip-net 10.10.0.17/32 --lb-port 80 --client-ip-net 10.10.1.0/24 --bottom-multi 1000 --top-multi 20000 --step-multi 1000 -d 15 -p 15 -n 1 --test-url 752.html --expected-payload-size 752
```
Запускаем тест с 1000 паралельных клиентов, каждые 15 секунд увеличиваем количество клиентов на 1000 и так до 20K пользователей. Размер ответа сервера -- 1460 байт
```
$ python3 test_proxy.py --backend-port 80 --backend-ip-net 10.10.0.17/32 --lb-ip-net 10.10.0.17/32 --lb-port 80 --client-ip-net 10.10.1.0/24 --bottom-multi 1000 --top-multi 20000 --step-multi 1000 -d 15 -p 15 -n 1 --test-url 1460.html --expected-payload-size 1460
```
* Замечание: для указания количества запросов в одном соединении используйте -n аргумент *
