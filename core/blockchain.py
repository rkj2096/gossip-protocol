import hashlib
import struct
import time
import numpy
import matplotlib.pyplot as plt
from networkx import nx_agraph, draw


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
                print ("block timestamp very old!")
                return valid_block, new_block
            # find previous block
            for j in range(len(self.block_chain) - 1, -1, -1):
                for k in range(0, len(self.block_chain[j])):
                    # print self.get_sha256(self.block_chain[j][k]), block[0]
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
        graph = nx_agraph.Graph()
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
        draw(graph, with_labels=True, pos=node_pos)
        plt.show()
