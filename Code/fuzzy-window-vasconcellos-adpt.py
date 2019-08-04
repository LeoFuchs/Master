import graphviz
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import os
from itertools import islice

from graphviz import Graph
import numpy as np


def window(seq, n):
    """Returns a sliding window (of width n) over data from the iterable
    """

    it = iter(seq)
    result = tuple(islice(it, n))

    if len(result) == n:
        yield result

    for elem in it:
        result = result[1:] + (elem,)
        yield result

def snowballing():
    """It generates the graph that presenting the Gold Standard (GS)
       snowballing and which GS items were found when analyzing
       the results.

   Args:
       results_list: List with the numbers of the articles of the
           GS found, that will be used in the formulation of
           the final graph.
       min_df: The minimum number of documents that a term
           must be found in.
       number_topics: Number of topics that the Latent
           Dirichlet Allocation (LDA) algorithm should return.
       number_words: Number of similar words that will be used
           to add the search string.
       enrichment: Number of rich terms that were used in the
           search string.

   Returns:
   """

    with open('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/GS.csv', mode='r') as gs:

        # Skipping the GS.csv line written 'title'
        next(gs)

        # Creating a list where each element is the name of a GS article, without spaces, capital letters and '-'
        #title_list = [line.strip().lower().replace(' ', '').replace('-', '') for line in gs]
        title_list = [line.strip().lower().replace(' ', '').replace('.', '') for line in gs]
        #title_list = [line.strip().lower( ).replace(' ', '').replace('-', '').replace(':', '').replace('\'', '').replace(',', '').replace('?', '').replace('s', '') for line in gs]
        #print("Compact Title List: " + str(title_list))

    gs.close()

    adjacency_matrix = np.zeros((len(title_list), len(title_list)))
    #print(adjacency_matrix)

    final_edges = []

    # Analyzing the citations of each of the articles
    for i in range(1, len(title_list) + 1):
        article_name = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/GS-pdf/%d.cermtxt' % i
        with open('%s' % article_name, mode='r') as file_zone:
            reader = file_zone.read().strip().lower().replace('\n', ' ').replace('\r', '').replace(' ', '').replace('.', '')
            for j in range(1, len(title_list) + 1):
                window_size = len(title_list[j-1])
                options = ["".join(x) for x in window(reader, window_size)]

                if i != j:
                    ratio = process.extractOne(title_list[j-1], options)
                    print("Ratio: (" + str(i) + " - " + str(j) + "): " + str(ratio))
                    if ratio is not None:
                        if ratio[1] >= 90:

                            auxiliar_list = [i, j]
                            final_edges.append(auxiliar_list)

                            adjacency_matrix[i-1][j-1] = 1
                            adjacency_matrix[j-1][i-1] = 1

            file_zone.close()

    print ("Final edges:" + str(final_edges))
    return title_list, adjacency_matrix, final_edges

def graph(results_list, title_list, adjacency_matrix, final_edges):

    # Creating an auxiliary list of size n in the format [1, 2, 3, 4, 5, ..., n]
    node_list = range(1, len(title_list) + 1)

    # Initializing the graph with its respective nodes
    g = Graph('Snowballing Graph', strict=True)
    for i in node_list:
        g.node('%02d' % i, shape='circle')

    for edge in final_edges:
        g.edge('%02d' % edge[0], '%02d' % edge[1])

    final_list = []

    for z in results_list:
        final_list.append(z)

    flag = 1

    while flag:
        flag = 0
        for i in range(0, len(title_list)):
            for k in final_list:
                if i+1 == k:
                    for j in range(0, len(title_list)):
                        if adjacency_matrix[i][j] == 1 and j+1 not in final_list:
                            final_list.append(j+1)
                            flag = 1
    for k in final_list:
        g.node('%02d' % k, shape='circle', color='red')

    for i in results_list:
        g.node('%02d' % i, shape='circle', color='blue')

    min_df = 4

    g.attr(label=r'\nGraph with search results for min_df = %d, number_topics =d, number_words =d and '
                 r'enrichment =d.\n Blue nodes were found in the search step in digital bases, red nodes were found '
                 r'through snowballing and black nodes were not found.' % min_df)
    g.attr(fontsize='12')

    r = graphviz.Source(g, filename="graph",
                        directory='/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/Snowballing/', format="ps")
    # r.render()
    r.view()

    return len(final_list)


def  main():
    """Main function."""
    results_list = [1, 2]

    print("Loading CERMINE...\n")
    cermine = "java -cp cermine-impl-1.14-20180204.213009-17-jar-with-dependencies.jar " \
              "pl.edu.icm.cermine.ContentExtractor -path " \
              "/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/GS-pdf -outputs text "
    os.system(cermine)
    print("Done!")

    print("Doing Snowballing...\n")
    title_list, adjacency_matrix, final_edges = snowballing()
    print("Done!")

    counter = graph(results_list, title_list, adjacency_matrix, final_edges)

if __name__ == "__main__":
    main()
