import logging
import pickle
import random
import numpy
import socket
import time
from collections import defaultdict
from threading import Condition, Lock, Thread

from .blockchain import Blockhain


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
            receive_thread = Thread(target=self.receive, args=(peer_id, peer_socket, ))
            receive_thread.daemon = True
            receive_thread.start()
            logging.info("%s -> %s" % (self, peer_id))
            self.connections.append(peer_socket)

        # listen for peers want to connect
        self.listening_socket.listen(5)
        while True:
            peer_socket, address = self.listening_socket.accept()
            peer = peer_socket.recv(4096).decode('utf-8')
            receive_thread = Thread(target=self.receive, args=(peer, peer_socket, ))
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
                if message == "START-MN":
                    # start mining: happen only once
                    mine_thread = Thread(target=self.mine)
                    mine_thread.daemon = True
                    mine_thread.start()
                    self.send(message, peer_socket)
                    self.messages_lock.release()
                else:
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
    
    def start_mining(self):
        # send all client START-MN message
        self.send(bytes('START-MN', 'utf-8'), None)
        self.messages['START-MN'] = True
    
    def longest_chain(self):
        print("Calculating longest chain...")
        self.messages_lock.acquire()
        total_blocks = 0
        for blocks in self.block_chain.block_chain:
            total_blocks += len(blocks)
        print ("Total blocks: %d, Blocks in longest chain: %d" % (total_blocks, len(self.block_chain.block_chain)))
        self.messages_lock.release()
        self.block_chain.tree()

    def __str__(self):
        return "%s:%s" % (self.ip, self.port)
