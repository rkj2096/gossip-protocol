import configparser
import logging
import os
from core.client import Client

from core.seed import Seed

logging.basicConfig(format='%(asctime)s:%(message)s', filename='logs/seed.log', filemode='w', level=logging.DEBUG)
logging.basicConfig(format='%(message)s', filename='logs/client.log', filemode='a', level=logging.DEBUG)

config_path = os.environ.get('GOSSIP.CONFIG_PATH', 'gossip_settings.ini')

config = configparser.ConfigParser()
config.read(config_path)

seed = config.defaults()['seeds']
client_configs = config.defaults()['clients']

# just one seed
seed_ip, seed_port = config[seed].get('ip'), config[seed].getint('port', 9000)
seed = Seed(seed_ip, seed_port)
seed.start()

clients = []
for client_key in client_configs.split(','):
    client_config = config[client_key]
    client = Client(client_config.get('ip'), client_config.getint('port'), seed_ip, seed_port, 
                    client_config.getfloat('hash_power'), client_config.getint('inter_arrival_time'), client_config.getint('random_seed'))
    clients.append(client)
    client.start()

clients[::-1].start_mining()

    
