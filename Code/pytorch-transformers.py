# Font: https://huggingface.co/pytorch-transformers/quickstart.html
import torch
import numpy as np
from pytorch_transformers import BertTokenizer, BertForMaskedLM

import glob
import gensim
import Levenshtein
import csv
import pandas as pd
import graphviz
import os

from itertools import islice
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.datasets import load_files
from fuzzywuzzy import process
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


def enrichment_words(word):

    # Load pre-trained model tokenizer (vocabulary)
    tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

    # Tokenize input
    read_files = glob.glob(
        "/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/QGS-txt/metadata-enrichment/txt/*.txt")

    with open("result.txt", "wb") as merge_files:
        for f in read_files:
            with open(f, "rb") as infile:
                merge_files.write(infile.read())

    merge_files.close()

    with open("result.txt", "r") as metadata_file:
        text = metadata_file.read().strip()
        text = text.replace('\r\n', '')

    sentences = [sentence + '.' for sentence in text.split('.') if word in sentence]

    counter = 1

    formated_sentences = "[CLS] "
    for i in sentences:
        if counter <= 2:
            formated_sentences += i + " [SEP]"
            counter = counter + 1
    # print("Sentence: " + str(formated_sentences))

    tokenized_text = tokenizer.tokenize(formated_sentences)
    # print("Tokenized Text: " + str(tokenized_text))

    # Defining the masked index equal the word of input

    masked_index = 0
    for count, token in enumerate(tokenized_text):
        if word in token:
            masked_index = count
            # print ("Masked Index: " + str(masked_index))

            # Mask a token that we will try to predict back with `BertForMaskedLM`
            # original_word = tokenized_text[masked_index]
            # print("Original Word: " + str(original_word))

            tokenized_text[masked_index] = '[MASK]'
            # print("New Tokenized Text: " + str(tokenized_text))

    # Convert token to vocabulary indices
    indexed_tokens = tokenizer.convert_tokens_to_ids(tokenized_text)
    # print("Indexed Tokens: " + str(indexed_tokens))
    # SEP = 102

    # Define sentence A and B indices associated to 1st and 2nd sentences (see paper)
    len_first = tokenized_text.index("[SEP]")
    segments_ids = [0] * len_first + [1] * (len(tokenized_text) - len_first)

    # print("Segments IDs: " + str(segments_ids))

    # Convert inputs to PyTorch tensors
    tokens_tensor = torch.tensor([indexed_tokens])
    segments_tensors = torch.tensor([segments_ids])

    # Load pre-trained model (weights)
    model = BertForMaskedLM.from_pretrained('bert-base-uncased')
    model.eval()

    # Predict all tokens
    with torch.no_grad():
        outputs = model(tokens_tensor, token_type_ids=segments_tensors)
        predictions = outputs[0]

    # Predict the five first possibilities of the word removed
    predicted_index = torch.topk(predictions[0, masked_index], 30)[1]
    predicted_index = list(np.array(predicted_index))
    # print("Predicted Index: " + str(predicted_index))

    predicted_tokens = tokenizer.convert_ids_to_tokens(predicted_index)
    predicted_tokens = [str(string) for string in predicted_tokens]
    # print("Predicted Word: " + str(predicted_tokens))

    return predicted_tokens


# similar_word = enrichment_words(feature_names[i])

def string_formulation(model, feature_names, number_words, number_topics, similar_words, levenshtein_distance,
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

        for topic_index, topic in enumerate(model.components_):
            counter = 0
            message += "("

            for i in topic.argsort()[:-number_words - 1:-1]:
                counter = counter + 1

                message += "(\""
                message += "\" - \"".join([feature_names[i]])

                if " " not in feature_names[i]:
                    try:
                        similar_word = enrichment_words(feature_names[i])
                        # print("Similar word:" + str(similar_word))

                        stem_feature_names = lancaster.stem(feature_names[i])
                        # print("stem feature names:", stem_feature_names)

                        stem_similar_word = []

                        final_stem_similar_word = []
                        final_similar_word = []

                        for j in similar_word:
                            stem_similar_word.append(lancaster.stem(j))
                        # print("stem Similar Word:", stem_similar_word)

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


def main():
    """Main function."""

    levenshtein_distance = 3
    lda_iterations = 5000

    qgs_txt = '/home/fuchs/Documentos/MESTRADO/Masters/Files-QGS/revisao-vasconcellos/QGS-txt/metadata'

    pubyear = 2015  # Pubyear = 0 --> disable

    min_df_list = [0.4]
    number_topics_list = [3]
    number_words_list = [2]
    enrichment_list = [0, 1, 2, 3]

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
                                                    levenshtein_distance, pubyear)

                        print("String with " + str(enrichment) + " similar words: " + str(string))
                        print("\n")

    file_output.close()


if __name__ == "__main__":
    main()
