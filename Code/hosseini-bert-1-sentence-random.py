# encoding: utf-8
# run with python automatic-script-vasconcellos.py >> vasconcellos-out.txt
import torch
import Levenshtein
import csv
import pandas as pd
import numpy as np
import graphviz
import glob
import os
import shutil
import random
import sys

from itertools import islice
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.datasets import load_files
from fuzzywuzzy import process
from pytorch_transformers import BertTokenizer, BertForMaskedLM
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


def string_formulation(model, feature_names, number_words, number_topics, similar_words, levenshtein_distance,
                       pubyear, bert_model, bert_tokenizer):
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
        pubyear: Search year delimiter.
        bert_tokenizer:
        bert_model:

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

        for topic_index, topic in enumerate(model.components_):
            counter = 0
            message += "("

            for i in topic.argsort()[:-number_words - 1:-1]:
                counter = counter + 1

                message += "(\""
                message += "\" - \"".join([feature_names[i]])

                if " " not in feature_names[i]:
                    try:
                        similar_word = enrichment_words(feature_names[i], bert_model, bert_tokenizer)
                        # print("Similar Word:", similar_word)

                        # Error if the word searched it's not presented in the tokens
                        if similar_word == ['error']:
                            pass
                        else:
                            stem_feature_names = lancaster.stem(feature_names[i])
                            # print("Stemming Feature Names:", stem_feature_names)

                            stem_similar_word = []

                            final_stem_similar_word = []
                            final_similar_word = []

                            for j in similar_word:
                                stem_similar_word.append(lancaster.stem(j))
                            # print("Stemming Similar Word:", stem_similar_word)

                            for number, word in enumerate(stem_similar_word):
                                if stem_feature_names != word and Levenshtein.distance(str(stem_feature_names),
                                                                                       str(word)) > levenshtein_distance:
                                    irrelevant = 0

                                    for k in final_stem_similar_word:
                                        if Levenshtein.distance(str(k), str(word)) < levenshtein_distance:
                                            irrelevant = 1

                                    if irrelevant == 0:
                                        final_stem_similar_word.append(word)
                                        final_similar_word.append(similar_word[number])

                            # print("Final Stemming Similar Word:", final_stem_similar_word)
                            # print("Final Similar Word:", final_similar_word)

                            message += "\" OR \""
                            if len(final_similar_word) < similar_words:
                                message += "\" OR \"".join(final_similar_word[m] for m in
                                                           range(0, len(final_similar_word)))
                            else:
                                message += "\" OR \"".join(final_similar_word[m] for m in
                                                           range(0, similar_words))

                    except Exception as e:
                        print ("Exception: " + str(e))

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


def enrichment_words(word, bert_model, bert_tokenizer):
    """Formulate the enrichment words for using in the search string.

        Args:
            word: Word that will be used to find as similar
            bert_model: Bert Model loading with the choosed parametrers in main function.
            bert_tokenizer: Bert Tokenizer used to create sentence tokenization via BERT.
        Return:
            predicted_tokens: List with the enrichement words.
    """

    # Tokenize input
    read_files = glob.glob(
        "/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/QGS-txt/metadata-enrichment/txt/*.txt" % author)

    # Merge all the files in one file named 'sentences.txt'
    with open("sentences.txt", "w") as merge_files:
        for f in read_files:
            with open(f, "r") as infile:
                merge_files.write(infile.read())

    merge_files.close()

    # Manipulating the file 'sentences.txt', replacing line breaks for #.
    with open("sentences.txt", "r") as metadata_file:
        text = metadata_file.read().strip()
        text = text.replace('\r\n', '#.')

    metadata_file.close()

    # print("Word: " + str(word))
    # print("Text: " + str(text))

    all_sentences = []
    selected_sentences = []
    for sentence in text.split('.'):
        all_sentences.append(sentence)

    # Treatment for if the selected sentence is the last sentence of the text (return only one sentence)
    # Treatment for one sentence.
    for sentence in all_sentences:
        if word in sentence:
            selected_sentences.append(sentence + '.')
            break
        elif word in sentence.lower():
            selected_sentences.append(sentence + '.')
            break

    # print("Selected Sentences:" + str(selected_sentences))

    formated_sentences = "[CLS] "
    for sentence in selected_sentences:
        formated_sentences += sentence.lower() + " [SEP] "
    # print("Formated Sentences: " + str(formated_sentences))

    tokenized_text = bert_tokenizer.tokenize(formated_sentences)
    # print("Tokenized Text: " + str(tokenized_text))

    # Defining the masked index equal the word of input
    masked_index = 0
    mark = 0

    for count, token in enumerate(tokenized_text):
        if word in token.lower():
            masked_index = count
            # print ("Masked Index: " + str(masked_index))

            # Mask a token that we will try to predict back with `BertForMaskedLM`
            # original_word = tokenized_text[masked_index]
            # print("Original Word: " + str(original_word))

            tokenized_text[masked_index] = '[MASK]'
            # print("New Tokenized Text: " + str(tokenized_text))

            mark = 1

    # Mark for return if the word it's not presented in tokens
    if mark == 0:
        return ['error']

    # Convert token to vocabulary indices
    indexed_tokens = bert_tokenizer.convert_tokens_to_ids(tokenized_text)
    # print("Indexed Tokens: " + str(indexed_tokens))

    # Define sentence A and B indices associated to 1st and 2nd sentences (see paper)
    len_first = tokenized_text.index("[SEP]")
    len_first = len_first + 1
    segments_ids = [0] * len_first + [1] * (len(tokenized_text) - len_first)

    # print("Segments IDs: " + str(segments_ids))
    # print("\n")

    # Convert inputs to PyTorch tensors
    tokens_tensor = torch.tensor([indexed_tokens])
    segments_tensors = torch.tensor([segments_ids])

    # Predict all tokens
    with torch.no_grad():
        outputs = bert_model(tokens_tensor, token_type_ids=segments_tensors)
        predictions = outputs[0]

    # Predict the five first possibilities of the word removed
    predicted_index = torch.topk(predictions[0, masked_index], 30)[1]
    predicted_index = list(np.array(predicted_index))
    # print("Predicted Index: " + str(predicted_index))

    # Remove the \2022 ascii error index
    for index in predicted_index:
        if index == '1528':
            predicted_index.remove('1528')

    predicted_tokens = bert_tokenizer.convert_ids_to_tokens(predicted_index)
    # print("Predicted Word: " + str(predicted_tokens))

    return predicted_tokens


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
    results = 3000
    key = '7f59af901d2d86f78a1fd60c1bf9426a'
    scopus = Scopus(key)

    try:
        search_df = scopus.search(string, count=results, view='STANDARD', type_=1)
        # print("number of results without improvement:", len(search_df))
    except Exception as e:
        print ("Exception: " + str(e))
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
    gs = pd.read_csv('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/GS.csv' % author, sep='\t')

    qgs = pd.read_csv('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/QGS.csv' % author, sep='\t')

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
    for len_qgs, l in enumerate(open('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/QGS.csv' % author)):
        pass
    for len_result, l in enumerate(open('/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/Result.csv')):
        pass

    list_qgs = []
    list_result = []

    counter_improvement = 0

    if len_result == 0:
        return counter_improvement

    for i in range(0, len_qgs):
        list_qgs.append(qgs.iloc[i, 0].lower())

    # print("QGS List:", list_qgs)
    # print("QGS List Size:", len(list_qgs))

    for i in range(0, len_result):
        list_result.append(result_name_list.iloc[i, 0].lower())

    # print("List Result:", list_result)
    # print("List Result Size:", len(list_result))

    train_set = [list_qgs, list_result]
    train_set = [val for sublist in train_set for val in sublist]

    # print("Train Set List:", train_set)
    # print("Train Set List Size", len(train_set))

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

    # print("Number of QGS articles founded (with improvement):", counter_improvement)

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
    for len_gs, l in enumerate(open('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/GS.csv' % author)):
        pass
    for len_result, l in enumerate(open('/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/Result.csv')):
        pass

    list_gs = []
    list_result = []

    list_graph = []

    counter_improvement = 0

    if len_result == 0:
        return counter_improvement, list_graph

    for i in range(0, len_gs):
        list_gs.append(gs.iloc[i, 0].lower())

    # print("GS List:", list_gs)
    # print("GS List Size:", len(list_gs))

    for i in range(0, len_result):
        list_result.append(result_name_list.iloc[i, 0].lower())

    # print("Result List:", list_result)
    # print("Result List Size:", len(list_result))

    train_set = [list_gs, list_result]
    train_set = [val for sublist in train_set for val in sublist]

    # print("Train Set List:", train_set)
    # print("Train Set List Size", len(train_set))

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

    # print("Number of GS articles founded (with improvement):", counter_improvement)

    return counter_improvement, list_graph


def window(seq, n):
    """Returns a sliding window (of width n) over data from the iterable

    Args:
        seq: String with the sequence of words
        n: Size of the window
    Returns:
        result: ...
    """

    it = iter(seq)
    result = tuple(islice(it, n))

    if len(result) == n:
        yield result

    for elem in it:
        result = result[1:] + (elem,)
        yield result


def snowballing():
    """Doing the snowballing of the articles presented in GS (Gold Standard).

   Args:

   Returns:
       title_list:
       adjacency_matrix:
       final_edges:
   """

    with open('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/GS.csv' % author, mode='r') as gs:

        # Skipping the GS.csv line written 'title'
        next(gs)

        # Creating a list where each element is the name of a GS article, without spaces, capital letters and '-'
        title_list = [line.strip().lower().replace(' ', '').replace('.', '') for line in gs]
        # print("Compact Title List: " + str(title_list))

    gs.close()

    adjacency_matrix = np.zeros((len(title_list), len(title_list)))
    # print(adjacency_matrix)

    final_edges = []

    # Analyzing the citations of each of the articles
    for i in range(1, len(title_list) + 1):
        article_name = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/GS-pdf/%d.cermtxt' % (author, i)
        with open('%s' % article_name, mode='r') as file_zone:
            reader = file_zone.read().strip().lower().replace('\n', ' ').replace('\r', ''). \
                replace(' ', '').replace('.', '')
            for j in range(1, len(title_list) + 1):
                window_size = len(title_list[j - 1])
                options = ["".join(x) for x in window(reader, window_size)]

                if i != j:
                    ratio = process.extractOne(title_list[j - 1], options)
                    # print("Ratio: (" + str(i) + " - " + str(j) + "): " + str(ratio))
                    if ratio is not None:
                        if ratio[1] >= 90:
                            auxiliar_list = [i, j]
                            final_edges.append(auxiliar_list)

                            adjacency_matrix[i - 1][j - 1] = 1
                            adjacency_matrix[j - 1][i - 1] = 1

            file_zone.close()

    # print ("Final edges:" + str(final_edges))
    return title_list, adjacency_matrix, final_edges


def graph(results_list, title_list, adjacency_matrix, final_edges, min_df, number_topics, number_words, enrichment):
    """Print the graph with the black, red and blue nodes.

    Args:
        results_list: List with the nodes founded in the search.
        title_list: List with the title of que GS files.
        adjacency_matrix: Adjacency Matrix for the representation
            of the edges.
        final_edges: List of lists with the node couples with need a edge.
        min_df: The minimum number of documents that a term must be found in.
        number_topics: Number of topics that the Latent
            Dirichlet Allocation (LDA) algorithm should return.
        number_words: Number of words that will be broken down
            in each topic.
        enrichment: Number of enrichments added to search string.

    Returns:
        final_list: Length of the final list with the articles
            founded in GS.
       """
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
                if i + 1 == k:
                    for j in range(0, len(title_list)):
                        if adjacency_matrix[i][j] == 1 and j + 1 not in final_list:
                            final_list.append(j + 1)
                            flag = 1
    for k in final_list:
        g.node('%02d' % k, shape='circle', color='red')

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


def randomize_qgs(qgs_size, gs_size):
    """Randomizing the articles that will be present in QGS from GS.

    Args:
        qgs_size:
        gs_size:
    Returns:

    """

    # List with the numbers of the random articles in GS that integrate the QGS
    random_list = random.sample(range(1, gs_size + 1), qgs_size)
    random_list.sort()
    print(random_list)

    # Delete all the files in the QGS folder before the randomization
    folder_meta = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/QGS-txt/metadata/txt/' \
                  % author
    for the_file in os.listdir(folder_meta):
        file_path = os.path.join(folder_meta, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print ("Exception: " + str(e))

    folder_enrich = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/QGS-txt/metadata-enrichment/txt/' \
                    % author
    for the_file in os.listdir(folder_enrich):
        file_path = os.path.join(folder_enrich, the_file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print ("Exception: " + str(e))

    # Copy files from the GS folder to the QGS folder
    for i in random_list:
        chosed_file_meta = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/GS-txt/metadata/txt/%d.txt' \
                           % (author, i)

        chosed_file_enrich = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/GS-txt/metadata-enrichment' \
                             '/txt/%d.txt' % (author, i)

        shutil.copy2(chosed_file_meta, folder_meta)
        shutil.copy2(chosed_file_enrich, folder_enrich)

    if os.path.exists('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/QGS.csv' % author):
        os.remove('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/QGS.csv' % author)

    with open('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/GS.csv' % author, mode='r') as gs:

        # Skipping the GS.csv line written 'title'
        next(gs)

        # Creating a list where each element is the name of a GS article, without spaces, capital letters and '-'
        title_list = [line.strip() for line in gs]

    gs.close()

    with open('/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/QGS.csv' % author, mode='wr') as qgs:

        # Skipping the GS.csv line written 'title'
        qgs.write('title')

        for i, line in enumerate(title_list):
            if i + 1 in random_list:
                qgs.write('\n')
                qgs.write(line)

    qgs.close()


def main():
    """Main function."""

    reload(sys)
    sys.setdefaultencoding('utf-8')

    global author

    levenshtein_distance = 4
    lda_iterations = 5000

    min_df_list = [0.1, 0.2, 0.3, 0.4]
    number_topics_list = [1, 2, 3, 4, 5]
    number_words_list = [5, 6, 7, 8, 9, 10]
    enrichment_list = [0, 1, 2, 3]

    author = 'hosseini'
    pubyear = 2016  # Pubyear = 0 --> disable
    qgs_size = 15
    gs_size = 46

    qgs_txt = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/QGS-txt/metadata' % author

    # Running CERMINE
    print("Loading CERMINE...\n")
    cermine = "java -cp cermine-impl-1.14-20180204.213009-17-jar-with-dependencies.jar " \
              "pl.edu.icm.cermine.ContentExtractor -path " \
              "/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-%s/GS-pdf/ -outputs text" % author
    os.system(cermine)

    print("Randomize QGS...\n")
    randomize_qgs(qgs_size, gs_size)

    print("Doing Snowballing...\n")
    title_list, adjacency_matrix, final_edges = snowballing()

    print("Loading BERT...\n")
    # Load pre-trained model tokenizer (vocabulary)
    bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

    # Load pre-trained model (weights)
    bert_model = BertForMaskedLM.from_pretrained('bert-base-uncased')
    bert_model.eval()

    with open('/home/fuchs/Documentos/MESTRADO/Masters/Code/Exits/%s-result.csv' % author, mode='w') as file_output:

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
                                                    levenshtein_distance, pubyear, bert_model, bert_tokenizer)

                        scopus_number_results = scopus_search(string)

                        qgs, gs, result_name_list, manual_comparation = open_necessary_files()
                        counter_one = similarity_score_qgs(qgs, result_name_list, manual_comparation)
                        counter_two, list_graph = similarity_score_gs(gs, result_name_list, manual_comparation)

                        counter_total = graph(list_graph, title_list, adjacency_matrix, final_edges,
                                              min_df, number_topics, number_words, enrichment)

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
