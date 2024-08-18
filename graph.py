import matplotlib.pyplot as plt
from networkx import nx_agraph, draw

graph = nx_agraph.Graph()
for line in open('client.log', 'r'):
    edge = line.strip("\n").split(" -> ")
    print(edge)
    graph.add_edge(edge[0], edge[1])
draw(graph, with_labels=True)
plt.show()
