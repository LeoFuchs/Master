# encoding: utf-8
# run with python automatic-script-vasconcellos.py >> vasconcellos-out.txt
import gensim
import Levenshtein
import csv
import pandas as pd
import numpy as np
import graphviz
import os

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.datasets import load_files
from nltk.stem import LancasterStemmer
from graphviz import Graph
from pyscopus import Scopus


def bag_of_words(min_df, qgs_txt):
    """Generates the Quasi-Gold Standard (QGS) bag-of-words representation.

    Args:
        min_df: The minimum number of documents that a term must be found in.
        qgs_txt: The folder with the Quasi-Gold Standard (QGS) files.

    Returns:
        dic: Dictionary with the most relevant words
        tf: Vectorized dataset with the bag-of-words
    """

    n_gram = (1, 3)
    max_document_frequency = 1.0
    min_document_frequency = min_df
    max_features = None

    # Load the training dataset (It's always in the Files-QGS folder).
    files = load_files(container_path=qgs_txt, encoding="iso-8859-1")

    # Extract the words and vectorize the dataset.
    tf_vectorizer = CountVectorizer(max_df=max_document_frequency,
                                    min_df=min_document_frequency,
                                    ngram_range=n_gram,
                                    max_features=max_features,
                                    stop_words='english')

    tf = tf_vectorizer.fit_transform(files.data)

    # Saves the names of the words in a dictionary.
    dic = tf_vectorizer.get_feature_names()

    return dic, tf


def lda_algorithm(tf, lda_iterations, number_topics):
    """Executes the algorithm of Latent Dirichlet Allocation (LDA)
    in the representation of bag-of-words generated by bag_of_words().

    Args:
        tf:
        lda_iterations: Number of iterations from the
            Latent Dirichlet Allocation (LDA) algorithm.
        number_topics: Number of topics that the Latent
            Dirichlet Allocation (LDA) algorithm should return.

    Return:
        lda: Return of the Latent Dirichlet Allocation (LDA)
            algorithm, broken down into topics pointed by
            the number_topics.
    """

    alpha = None
    beta = None
    learning = 'batch'  # Batch or Online

    # Run the Latent Dirichlet Allocation (LDA) algorithm and train it.
    lda = LatentDirichletAllocation(n_components=number_topics,
                                    doc_topic_prior=alpha,
                                    topic_word_prior=beta,
                                    learning_method=learning,
                                    learning_decay=0.7,
                                    learning_offset=10.0,
                                    max_iter=lda_iterations,
                                    batch_size=128,
                                    evaluate_every=-1,
                                    total_samples=1000000.0,
                                    perp_tol=0.1,
                                    mean_change_tol=0.001,
                                    max_doc_update_iter=100,
                                    random_state=0)

    lda.fit(tf)

    return lda


def string_formulation(model, feature_names, number_words, number_topics, similar_words, levenshtein_distance, wiki,
                       pubyear):
    """Formulate the search string based on the input parameters.

    Args:
        model: Return of the lda_algorithm() with the Latent
            Dirichlet Allocation (LDA) algorithm execution.
        feature_names: Dictionary generated by the bag-of-words
            representation.
        number_words: Number of words that will be broken down
            in each topic.
        number_topics: Number of topics that will be represented
            by the Latent Dirichlet Allocation (LDA).
        similar_words: Number of similar words that will be used
            to add the search string.
        levenshtein_distance: Distance of levenshtein used for
            comparison of titles.
        wiki: FastText database used by enrichment of terms
        pubyear: Search year delimiter.

    Return:
        message: Search string to be used.
    """
    global final_similar_word
    message = "TITLE-ABS-KEY("
    if similar_words == 0:
        for topic_index, topic in enumerate(model.components_):
            message += "(\""
            message += "\" AND \"".join([feature_names[i] for i in topic.argsort()[:-number_words - 1:-1]])
            message += "\")"

            if topic_index < number_topics - 1:
                message += " OR "
            else:
                message += ""

        message += ")"

        if pubyear != 0:
            message += " AND PUBYEAR < "
            message += str(pubyear)

        return message

    else:
        lancaster = LancasterStemmer()

        word2vec_total_words = 30

        for topic_index, topic in enumerate(model.components_):
            counter = 0
            message += "("

            for i in topic.argsort()[:-number_words - 1:-1]:
                counter = counter + 1

                message += "(\""
                message += "\" - \"".join([feature_names[i]])

                if " " not in feature_names[i]:
                    try:
                        similar_word = wiki.most_similar(positive=feature_names[i], topn=word2vec_total_words)
                        similar_word = [j[0] for j in similar_word]
                        # print("similar word:", similar_word)

                        stem_feature_names = lancaster.stem(feature_names[i])
                        # print("stem feature names:", stem_feature_names)

                        stem_similar_word = []

                        final_stem_similar_word = []
                        final_similar_word = []

                        for j in similar_word:
                            stem_similar_word.append(lancaster.stem(j))
                        # print("stem Similar Word:", stem_similar_word)

                        for number, word in enumerate(stem_similar_word):
                            if stem_feature_names != word and Levenshtein.distance(stem_feature_names,
                                                                                   word) > levenshtein_distance:
                                irrelevant = 0

                                for k in final_stem_similar_word:
                                    if Levenshtein.distance(k, word) < levenshtein_distance:
                                        irrelevant = 1

                                if irrelevant == 0:
                                    final_stem_similar_word.append(word)
                                    final_similar_word.append(similar_word[number])

                        # print("final stem similar word:", final_stem_similar_word)
                        # print("final similar word:", final_similar_word)

                        message += "\" OR \""
                        message += "\" OR \"".join(final_similar_word[m] for m in
                                                   range(0, similar_words))  # Where defined the number of similar words

                    except Exception as e:
                        print (e)

                message += "\")"

                if counter < len(topic.argsort()[:-number_words - 1:-1]):
                    message += " AND "
                else:
                    message += ""

            message += ")"

            if topic_index < number_topics - 1:
                message += " OR "
            else:
                message += ""

        message += ")"

        if pubyear != 0:
            message += " AND PUBYEAR < "
            message += str(pubyear)

        return message


def scopus_search(string):
    """Run the search string returned by the function
        string_formulation() in the digital library
        Scopus via pyscopus.

    Args:
        string: Search string to be used.

    Returns:
        search_df: Structure containing all search
            results in Scopus digital library
    """
    results = 5000
    key = '7f59af901d2d86f78a1fd60c1bf9426a'
    scopus = Scopus(key)

    try:
        search_df = scopus.search(string, count=results, view='STANDARD', type_=1)
        # print("number of results without improvement:", len(search_df))
    except Exception as e:
        print (e)
        return -1

    pd.options.display.max_rows = 99999
    pd.options.display.max_colwidth = 250

    search_df[['title']].to_csv("/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/Result.csv", index_label=False,
                                encoding='utf-8', index=False, header=True, sep='\t')

    return int(len(search_df))


def open_necessary_files():
    """Open the files that will be used in the program.

    Args:

    Returns:
        qgs: All the names of the articles contained in the QGS.
        gs: All the names of the articles contained in the GS.
        result_name_list: All the names of the articles contained
            in the search result in Scopus.
        manual_comparation: List for manual comparison of results
            found with results initially stored.
    """
    gs = pd.read_csv('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/GS.csv', sep='\t')

    qgs = pd.read_csv('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/QGS.csv', sep='\t')

    result_name_list = pd.read_csv('/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/Result.csv', sep='\t')
    result_name_list = result_name_list.fillna(' ')

    manual_comparation = open('/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/ManualExit.csv', 'w')

    return qgs, gs, result_name_list, manual_comparation


def similarity_score_qgs(qgs, result_name_list, manual_comparation):
    """It makes the automatic comparison between the Quasi-Gold Standard
        (QGS) and the results, obtaining the count of how many QGS
        articles are present in the result.

    Args:
        qgs: All the names of the articles contained in the QGS.
        result_name_list: All the names of the articles contained
            in the search result in Scopus.
        manual_comparation: List for manual comparison of results
            found with results initially stored.

    Returns:
        counter_improvement: Counter of articles contained in the
            search result that are in the QGS
    """
    len_qgs, len_result = 0, 0
    for len_qgs, l in enumerate(open('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/QGS.csv')):
        pass
    for len_result, l in enumerate(open('/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/Result.csv')):
        pass

    list_qgs = []
    list_result = []

    counter_improvement = 0

    for i in range(0, len_qgs):
        list_qgs.append(qgs.iloc[i, 0].lower())

    # print("qgs list:", list_qgs)
    # print("qgs list size:", len(list_qgs))

    for i in range(0, len_result):
        list_result.append(result_name_list.iloc[i, 0].lower())

    if len_result == 0:
        return counter_improvement

    # print("list result:", list_result)
    # print("list result size:", len(list_result))

    train_set = [list_qgs, list_result]
    train_set = [val for sublist in train_set for val in sublist]

    # print("train_set list:", train_set)
    # print("train_set list size", len(train_set))

    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix_train = tfidf_vectorizer.fit_transform(train_set)

    mat_similarity = cosine_similarity(tfidf_matrix_train[0:len_qgs],
                                       tfidf_matrix_train[len_qgs:len_qgs + len_result])
    lin, col = mat_similarity.shape

    for i in range(0, lin):

        line = mat_similarity[i]
        current_nearest = np.argsort(line)[-2:]  # Get the x-1 largest elements

        line_exit = 'QGS' + str(i + 1) + ':\t\t\t' + list_qgs[i] + '\t' + '\n'

        for j in range(1, len(current_nearest)):
            book = current_nearest[-j]
            line_exit = line_exit + '\t\t\t\t' + list_result[book].strip() + '\t' '\n'

            if Levenshtein.distance(list_qgs[i], list_result[book]) < 10:
                counter_improvement = counter_improvement + 1

        line_exit = line_exit + "\n"

        manual_comparation.write(line_exit)
        manual_comparation.flush()

    # print("number of QGS articles founded (with improvement):", counter_improvement)

    return counter_improvement


def similarity_score_gs(gs, result_name_list, manual_comparation):
    """It makes the automatic comparison between the Gold Standard
        (GS) and the results, obtaining the count of how many GS
        articles are present in the result.

    Args:
        gs: All the names of the articles contained in the QGS.
        result_name_list: All the names of the articles contained
            in the search result in Scopus.
        manual_comparation: List for manual comparison of results
            found with results initially stored.

    Returns:
        counter_improvement: Counter of articles contained in the
            search result that are in the GS
        list_graph: List with the numbers of the articles of the
            GS found, that will be used in the formulation of
            the final graph.
    """

    len_gs, len_result = 0, 0
    for len_gs, l in enumerate(open('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/GS.csv')):
        pass
    for len_result, l in enumerate(open('/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/Result.csv')):
        pass

    list_gs = []
    list_result = []

    list_graph = []

    counter_improvement = 0

    for i in range(0, len_gs):
        list_gs.append(gs.iloc[i, 0].lower())

    # print("gs list:", list_gs)
    # print("gs list size:", len(list_gs))

    for i in range(0, len_result):
        list_result.append(result_name_list.iloc[i, 0].lower())

    if len_result == 0:
        return counter_improvement

    # print("result list:", list_result)
    # print("result list size:", len(list_result))

    train_set = [list_gs, list_result]
    train_set = [val for sublist in train_set for val in sublist]

    # print("train_set list:", train_set)
    # print("train_set list size", len(train_set))

    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix_train = tfidf_vectorizer.fit_transform(train_set)

    mat_similarity = cosine_similarity(tfidf_matrix_train[0:len_gs], tfidf_matrix_train[len_gs:len_gs + len_result])
    lin, col = mat_similarity.shape

    for i in range(0, lin):

        line = mat_similarity[i]
        current_nearest = np.argsort(line)[-2:]  # Get the x-1 largest elements

        line_exit = 'GS' + str(i + 1) + ':\t\t\t' + list_gs[i] + '\t' + '\n'

        for j in range(1, len(current_nearest)):
            book = current_nearest[-j]
            line_exit = line_exit + '\t\t\t\t' + list_result[book].strip() + '\t' '\n'

            if Levenshtein.distance(list_gs[i], list_result[book]) < 10:
                counter_improvement = counter_improvement + 1
                list_graph.append(i + 1)

        line_exit = line_exit + "\n"

        manual_comparation.write(line_exit)
        manual_comparation.flush()

    # print("number of GS articles founded (with improvement):", counter_improvement)

    return counter_improvement, list_graph


def graph_snowballing(results_list, min_df, number_topics, number_words, enrichment):
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
        title_list = [line.strip().lower().replace(' ', '').replace('-', '') for line in gs]

    gs.close()

    # Creating an auxiliary list of size n in the format [1, 2, 3, 4, 5, ..., n]
    node_list = range(1, len(title_list) + 1)

    # Initializing the adjacency matrix with zeros
    adjacency_matrix = np.zeros((len(title_list), len(title_list)))

    # Initializing the graph with its respective nodes
    g = Graph('Snowballing Graph', strict=True)
    for i in node_list:
        g.node('%02d' % i, shape='circle')

    # Analyzing the citations of each of the articles
    for i in range(1, len(title_list) + 1):
        article_name = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/GS-pdf/%d.cermzones' % i
        with open('%s' % article_name, mode='r') as file_zone:

            # Manipulating the input file (REMOVE THIS I != 16 LATER)
            if i != 16:
                # Making all lowercase letters
                reader = file_zone.read().lower()

                # Removing line breaks
                reader = reader.strip().replace('\n', ' ').replace('\r', '')

                # Removing spaces and special characters
                reader = reader.replace(' ', '').replace('-', '')

                # Filtering only the part of the references in the zone file
                sep = "<zonelabel=\"gen_references\">"
                reader = reader.split(sep, 1)[1]
                # print(reader)

                for j in range(1, len(title_list) + 1):
                    if i != j:
                        if title_list[j - 1] in reader:
                            # print("the article GS-%02.d cite the article %02.d.\n" % (i, j))
                            g.edge('%02d' % i, '%02d' % j)
                            adjacency_matrix[i - 1][j - 1] = 1
                            adjacency_matrix[j - 1][i - 1] = 1
                            # g.edge('%02d' % j, '%02d' % i)
        file_zone.close()

    final_list = []

    for z in results_list:
        final_list.append(z)

    flag = 1

    while flag:
        flag = 0
        for i in range(0, len(title_list)):
            for k in final_list:
                if i + 1 == k:
                    for j in range(0, len(title_list)):
                        if adjacency_matrix[i][j] == 1 and j + 1 not in final_list:
                            final_list.append(j + 1)
                            flag = 1

    for i in final_list:
        g.node('%02d' % i, shape='circle', color='red')

    for i in results_list:
        g.node('%02d' % i, shape='circle', color='blue')

    g.attr(label=r'\nGraph with search results for min_df = %0.1f, number_topics = %d, number_words = %d and '
                 r'enrichment = %d.\n Blue nodes were found in the search step in digital bases, red nodes were found '
                 r'through snowballing and black nodes were not found.'
                 % (min_df, number_topics, number_words, enrichment))
    g.attr(fontsize='12')

    r = graphviz.Source(g, filename="graph-with-%0.1f-%d-%d-%d" % (min_df, number_topics, number_words, enrichment),
                        directory='/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/Snowballing/', format="ps")
    r.render()
    # r.view()

    return len(final_list)


def main():
    """Main function."""

    levenshtein_distance = 4
    lda_iterations = 5000

    qgs_txt = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/QGS-txt/metadata'

    pubyear = 2015  # Pubyear = 0 --> disable

    min_df_list = [0.4]
    number_topics_list = [3]
    number_words_list = [7]
    enrichment_list = [0, 1, 2, 3]

    # Running FastText
    print("Loading wiki...\n")
    wiki = gensim.models.KeyedVectors.load_word2vec_format(
        '/home/fuchs/Documentos/MESTRADO/Datasets/wiki-news-300d-1M.vec')

    # Running CERMINE
    print("Loading CERMINE...\n")
    cermine = "java -cp cermine-impl-1.13-jar-with-dependencies.jar pl.edu.icm.cermine.ContentExtractor -path " \
              "/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/GS-pdf/ -outputs zones "
    os.system(cermine)

    with open('/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/vasconcellos-result.csv', mode='w') as file_output:

        file_writer = csv.writer(file_output, delimiter=',')

        file_writer.writerow(['min_df', 'Topics', 'Words', 'Similar Words', 'No. Results',
                              'No. QGS', 'No. GS', 'No. Total'])

        for min_df in min_df_list:
            for number_topics in number_topics_list:
                for number_words in number_words_list:

                    print("Test with " + str(number_topics) + " topics and " + str(number_words) + " words in " + str(
                        min_df) + " min_df:")
                    print("\n")

                    dic, tf = bag_of_words(min_df, qgs_txt)
                    lda = lda_algorithm(tf, lda_iterations, number_topics)

                    for enrichment in enrichment_list:
                        string = string_formulation(lda, dic, number_words, number_topics, enrichment,
                                                    levenshtein_distance, wiki, pubyear)

                        scopus_number_results = scopus_search(string)

                        qgs, gs, result_name_list, manual_comparation = open_necessary_files()
                        counter_one = similarity_score_qgs(qgs, result_name_list, manual_comparation)
                        counter_two, list_graph = similarity_score_gs(gs, result_name_list, manual_comparation)

                        counter_total = graph_snowballing(list_graph, min_df, number_topics, number_words, enrichment)

                        file_writer.writerow(
                            [min_df, number_topics, number_words, enrichment, scopus_number_results, counter_one,
                             counter_two, counter_total])

                        print("String with " + str(enrichment) + " similar words: " + str(string))
                        print("Generating " + str(scopus_number_results) + " results with " +
                              str(counter_one) + " of the QGS articles, " + str(counter_two) +
                              " of the GS articles (without snowballing) and " + str(counter_total) +
                              " of the GS articles (with snowballing).")
                        print("\n")

    file_output.close()


if __name__ == "__main__":
    main()
