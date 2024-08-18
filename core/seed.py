import sys
import socket
import pickle
import signal
import logging


class Seed:
    def __init__(self, ip, port):
        """
        Create a seed node
        :param ip: ip address of seed
        :param port: port number of seed
        """
        self.ip = ip
        self.port = int(port)
        self.client_list = {}
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((self.ip, self.port))
        signal.signal(signal.SIGINT, self.stop)

    def start(self):
        """
        Start seed node listen to address <ip:port>
        :return:
        """
        self.server.listen(5)
        logging.info("Seed listening at: %s" % self)
        while True:
            client_socket, address = self.server.accept()
            message = client_socket.recv(4096).decode('utf-8')
            client = message.split(":")
            client = (client[0], int(client[1]))
            logging.info("New Client: %s" % message)
            # send client-list to new client
            client_socket.send(pickle.dumps(self.client_list))
            # check if client is not in client list add
            if message not in self.client_list.keys():
                self.client_list[message] = client
            client_socket.close()

    def stop(self, signum, frame):
        """
        Stop seed node save client-list
        :param signum:
        :param frame:
        :return:
        """
        self.server.close()
        with open('client_list.pkl', 'wb') as f:
            pickle.dump(self.client_list, f)

    def resume(self):
        """
        Start a seed node with previous client-list
        :return:
        """
        with open('client_list.pkl', 'rb') as f:
            self.client_list = pickle.load(f)
        self.start()

    def __str__(self):
        return "%s:%d" % (self.ip, self.port)


if __name__ == '__main__':
    logging.basicConfig(format='%(asctime)s:%(message)s', filename='seed.log', filemode='w', level=logging.DEBUG)
    ip = sys.argv[1]
    port = sys.argv[2]
    seed = Seed(ip, port)
    seed.start()
