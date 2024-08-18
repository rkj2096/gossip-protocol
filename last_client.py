import random
import sys
import pickle
import socket
import logging
import time
import hashlib
import struct
import networkx 
import numpy
import matplotlib.pyplot as plt
from collections import defaultdict
from threading import Thread, Lock, Condition


class Blockhain:
    def __init__(self):
        """
        Create a block-chain with a genesis block with hash 0x9e1c
        """
        self.genesis_hash = 0x9e1c
        self.block_chain = []

    def get_sha256(self, message):
        """
        Generate sha256 hash of message and return last 16 bits
        :param message: string or buffer
        :return: sha256 last 16 bits
        """
        return int(hashlib.sha256(message).hexdigest(), 16) & 0xffff

    def get_prev_block_hash(self):
        """
        It returns the hash of latest block user should mine on
        :return: sha256 hash
        """
        if len(self.block_chain) == 0:
            prev_block_hash = self.genesis_hash
        else:
            prev_block = self.block_chain[-1][0]
            prev_block_hash = self.get_sha256(prev_block)
        return prev_block_hash

    def generate_block(self):
        """
        Generate a block after longest chain
        :return: block
        """
        prev_block_hash = self.get_prev_block_hash()
        merkel_root = numpy.random.randint(0, 0xffff)
        timestamp = int(time.time())
        # print prev_block_hash, merkel_root, timestamp
        block = struct.pack('HHI', prev_block_hash, merkel_root, timestamp)
        self.block_chain.append([block])
        return block

    def verify_and_add_block(self, message):
        """
        Verify and append a received block at appropriate place in block-chain
        :param message: received block
        :return: true if added successfully
        """
        valid_block, new_block = False, False
        try:
            block = struct.unpack('HHI', message)
            # check block timestamp
            if abs(int(time.time() - block[2])) > 3600:
                print("block timestamp very old!")
                return valid_block, new_block
            # find previous block
            for j in range(len(self.block_chain) - 1, -1, -1):
                for k in range(0, len(self.block_chain[j])):
                    if self.get_sha256(self.block_chain[j][k]) == block[0]:
                        valid_block = True
                        if j + 1 < len(self.block_chain):
                            self.block_chain[j+1].append(message)
                        else:
                            self.block_chain.append([message])
                            new_block = True
                        return valid_block, new_block
            # check if it's just after genesis block
            if self.genesis_hash == block[0]:
                valid_block = True
                if len(self.block_chain) == 0:
                    self.block_chain.append([message])
                    new_block = True
                else:
                    self.block_chain[0].append(message)
                return valid_block, new_block
        except:
            print("Bad block: failed to unpack")
        return valid_block, new_block

    def tree(self):
        graph = networkx.nx.Graph()
        node_pos = {}
        for j in range(len(self.block_chain) - 1, 0, -1):
            for k in range(0, len(self.block_chain[j])):
                vertex1 = self.block_chain[j][k]
                for l in range(0, len(self.block_chain[j - 1])):
                    vertex2 = self.block_chain[j - 1][l]
                    if struct.unpack('HHI', vertex1)[0] == self.get_sha256(vertex2):
                        graph.add_edge("%d_%d" % (j, l), "%d_%d" % (j + 1, k))
                        node_pos["%d_%d" % (j, l)] = (j, l)
                        node_pos["%d_%d" % (j + 1, k)] = (j + 1, k)
        for i in range(len(self.block_chain[0])):
            graph.add_edge('genesis', "%d_%d" % (1, i))
            node_pos["genesis"] = (0, 0)
            node_pos["%d_%d" % (1, i)] = (1, i)
        networkx.nx.draw(graph, with_labels=True, pos=node_pos)
        plt.show()


class Client:
    def __init__(self, ip, port, seed_ip, seed_port, hash_power, inter_arrival_time, random_seed):
        """
        Create a client node
        :param ip: client ip address
        :param port: client port number
        :param seed_ip: seed node ip address
        :param seed_port: seed node port number
        """
        self.ip = ip
        self.port = int(port)
        self.seed_ip = seed_ip
        self.seed_port = int(seed_port)
        self.client_lambda = hash_power*(1.0/inter_arrival_time)
        self.connections = []
        self.messages = defaultdict(bool)
        self.messages_lock = Lock()
        self.new_block_received_cond = Condition()
        self.new_block_received = False
        self.block_chain = Blockhain()
        self.output_file = open("outputfile_%d.txt" % self.port, 'w')
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listening_socket.bind((self.ip, self.port))
        numpy.random.seed(random_seed)

    def start(self):
        """
        Start a client node at address <ip:port> connect to seed node fetch client-list and start tcp connection from some
        :return:
        """
        # fetch client-list from seed
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((self.seed_ip, self.seed_port))
        client_socket.send(bytes(self.__str__(), 'utf-8'))
        peers = pickle.loads(client_socket.recv(4096))
        # print and write to file the client list
        print ("Client List")
        print ("\n".join(peers.keys()))
        self.output_file.write("\n".join(peers.keys()))
        self.output_file.write("\n")

        # connect two random peers
        for peer_id, peer in random.sample(peers.items(), k=min(2, len(peers))):
            peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            peer_socket.connect(peer)
            peer_socket.sendall(bytes(self.__str__(), 'utf-8'))
            receive_thread = Thread(target=self.receive, args=(peer_id, peer_socket,))
            receive_thread.daemon = True
            receive_thread.start()
            logging.info("%s -> %s" % (self, peer_id))
            self.connections.append(peer_socket)

        # send all client START-MN message
        self.send(bytes('START-MN', 'utf-8'), None)
        self.messages['START-MN'] = True
        # start mining: happen only once
        mine_thread = Thread(target=self.mine)
        mine_thread.daemon = True
        mine_thread.start()

        # listen for peers want to connect
        self.listening_socket.listen(5)
        while True:
            peer_socket, address = self.listening_socket.accept()
            peer = peer_socket.recv(4096).decode()
            receive_thread = Thread(target=self.receive, args=(peer, peer_socket,))
            receive_thread.daemon = True
            receive_thread.start()
            self.connections.append(peer_socket)

    def receive(self, peer, peer_socket):
        """
        Receive message from peer node and if is not already present in Message List forward it all adjacent nodes
        :param peer: peer_id
        :param peer_socket: socket object of peer
        :return:
        """
        while True:
            # receive start
            size_to_receive = 8
            message = bytearray()
            while True:
                message.extend(peer_socket.recv(size_to_receive))
                if len(message) == 8:
                    break
                else:
                    size_to_receive = 8 - len(message)
            message = bytes(message)
            # receive end
            self.messages_lock.acquire()
            if not self.messages[message]:
                # print message & mark it true
                print ("Received: %d:%s->%s" % (int(time.time()), peer, message))
                self.messages[message] = True
                # a block received
                valid_block, new_block = self.block_chain.verify_and_add_block(message)
                self.messages_lock.release()
                # if new block received reset miner
                if new_block:
                    with self.new_block_received_cond:
                        self.new_block_received = True
                        self.new_block_received_cond.notify()
                # if valid block send it to all peers
                if valid_block:
                    self.send(message, peer_socket)
                self.output_file.write("%f:%s->%s\n" % (time.time(), peer, message))
            else:
                self.messages_lock.release()

    def send(self, message, peer_socket):
        """
        Send message to all adjacent peers
        :param message: message to be sent
        :param peer_socket: socket object of the peer message received from
        :return:
        """
        for connection in self.connections:
            # send if peer is not same as where it came from
            if connection != peer_socket:
                connection.sendall(message)

    def mine(self):
        """
        Send 10 messages every 5 seconds to all adjacent nodes
        :return:
        """
        while True:
            # wait till time-out or a new block in longest chain received
            with self.new_block_received_cond:
                waiting_time = numpy.random.exponential(1.0/self.client_lambda)
                print ("Timer: %fs" % waiting_time)
                self.new_block_received_cond.wait(timeout=waiting_time)
            # if new block received reset miner
            if self.new_block_received:
                self.new_block_received = False
            else:
                # mine a new block and broadcast it
                block = self.block_chain.generate_block()
                print ("Generated: %d:%s" % (int(time.time()), block))
                self.messages_lock.acquire()
                self.messages[block] = True
                self.messages_lock.release()
                self.send(block, None)

    def __str__(self):
        return "%s:%s" % (self.ip, self.port)


if __name__ == '__main__':
    logging.basicConfig(format='%(message)s', filename='client.log', filemode='a', level=logging.DEBUG)
    ip, port = sys.argv[1].split(":")
    seed_ip, seed_port = sys.argv[2].split(":")
    hashing_power = float(sys.argv[3])
    inter_arrival_time = int(sys.argv[4])
    random_seed = int(sys.argv[5])
    client = Client(ip, port, seed_ip, seed_port, hashing_power, inter_arrival_time, random_seed)
    try:
        client.start()
    except KeyboardInterrupt:
        print("Calculating...")
        client.messages_lock.acquire()
        total_blocks = 0
        for blocks in client.block_chain.block_chain:
            total_blocks += len(blocks)
        print ("Total blocks: %d, Blocks in longest chain: %d" % (total_blocks, len(client.block_chain.block_chain)))
        client.messages_lock.release()
        client.block_chain.tree()
        sys.exit(0)
