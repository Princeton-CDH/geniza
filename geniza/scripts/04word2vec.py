import sys
from collections import Counter
import textwrap
from glob import glob
from pprint import pprint
import os
import shutil
import logging
import pickle
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from itertools import cycle

import nltk
import pyLDAvis
import pyLDAvis.gensim_models
import gensim
import gensim.corpora as corpora
from gensim.utils import simple_preprocess
from gensim.models import CoherenceModel, Word2Vec
import spacy
from gensim.models.ldamodel import LdaModel
from nltk.collocations import BigramCollocationFinder, BigramAssocMeasures

from sklearn.cluster import AffinityPropagation
from sklearn import metrics

from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_samples, silhouette_score
from sklearn.decomposition import PCA

from ldamallet import LdaMallet
from utils import generate_cluster_size_figure

logger = logging.getLogger(__name__)


def process_words(texts, stop_words, disallowed_ners=None, min_len=3, max_len=30):
    # python -m spacy download en_core_web_sm
    # English pipeline optimized for CPU. Components: tok2vec, tagger, parser, senter, ner, attribute_ruler, lemmatizer.
    # Other pipelines at https://spacy.io/models/en
    nlp = spacy.load('en_core_web_sm')

    texts_out = []

    # implement lemmatization and filter out unwanted part of speech tags
    for i, sentence in enumerate(texts):
        doc = nlp(sentence)
        doctext = doc.text
        ents = list(doc.ents)

        if disallowed_ners is not None:
            # Filtering out disallowed NERs should be done prior to splitting the sentence using whitespace.
            disallowed_tokens = []
            for ent in ents:
                if ent.label_ in disallowed_ners:
                    disallowed_tokens.append(ent.text.lower())

        tokens = [token.lemma_ for token in doc]
        # simple_preprocess => lowercase; ignore tokens that are too short or too long
        tokens = [t for t in simple_preprocess(' '.join(tokens), deacc=False, min_len=min_len, max_len=max_len)
                  if t not in stop_words and t not in disallowed_tokens]
        texts_out.append(tokens)

    return texts_out


def plot_word2vec_model(model):
    words = list(model.wv.key_to_index)
    X = model.wv[words]
    pca = PCA(n_components=2)
    result = pca.fit_transform(X)
    plt.scatter(result[:, 0], result[:, 1])
    for i, word in enumerate(words):
        plt.annotate(word, xy=(result[i, 0], result[i, 1]))


def vectorize(list_of_docs, model):
    features = np.zeros((len(list_of_docs), model.vector_size))
    for i, tokens in enumerate(list_of_docs):
        vectors = [model.wv[token] for token in tokens if token in model.wv]
        if vectors:
            features[i, :] = np.mean(vectors, axis=0)

    return features


PARAMS = dict(
    MAX_DOCS=None,                    # for quick code testing - int or None (all docs)
    MIN_LEN=3,                        # words less than this length will be filtered
    MAX_LEN=100,                      # words more than this length will be filtered
    DISALLOWED_NERS=[                 # Named-entities to filter out
                                      # See https://github.com/explosion/spaCy/blob/b7ba7f78a28ef71fca60415d0165e27a058d1946/spacy/glossary.py#L318
        'PERSON',
        'GPE',
        'ORG'
    ],
    BIGRAM=False,                     # Form bigrams before creating corpus?
    BIGRAM_MIN_PMI=5,                 # Min. PMI in order to create bigrams (determine by manual inspection of generated bigrams.txt)
    BIGRAM_MIN_FREQ=20,               # Min. freq of co-occurring tokens before they can be considered a bigram

    COMMON_WORDS_MAX_FREQUENCY=10000,  # For root words, the max. frequency beyond which they're not useful
    COMMON_WORDS_MAX_DOCS=0.5,        # For root words, max docs (absolute or relative) beyond which they're not useful
    COMMON_WORDS_MIN_DOCS=5,          # For root words, min docs (absolute or relative) beyond which they're not useful

    KEEP_TOKENS=[],                   # Root words to preserve in the vocabulary regardless of their frequency (high or low)

    # No. of topics - numeric or a range
    K=range(10, 50),

    WORD2VEC_VECTOR_SIZE=200,
    WORD2VEC_WINDOW=10,
    WORD2VEC_EPOCHS=30,

    AFFINITY_N_DOCS=None,
    AFFINITY_DAMPING=0.8,

    # Parameters that determine initial preference values

    # How many tags to consider (most common to least common)
    AFFINITY_PREFERENCE_N_TAGS=100,
    # Specific tags to ignore when determining most common tags
    AFFINITY_PREFERENCE_BAD_TAGS=('arabic', 'arabic script', 'arabic address', 'arabic literary', 'fgp stub', 'late ja', 'late heb', 'illness letter 969–1517',
            '11th c', '12th c', '13th c', '16th c', '18th c', '19th c', '20th c', 'cudl', 'nahray b nissim'),

    AFFINITY_PREFERENCE_N_DESCRIPTIONS=20
)


def generate_html(docs_df, wv, af, X, output_dir, filename):
    cluster_centers_indices = af.cluster_centers_indices_
    n_clusters_ = len(cluster_centers_indices)
    logger.info(f'Estimated number of clusters: {n_clusters_}')

    labels = af.labels_
    with open(os.path.join(output_dir, filename), 'w') as f:
        for label in np.unique(labels):
            docs = np.where(labels == label)[0]
            docs_mean_vector = X[docs].mean(axis=0)
            terms = ', '.join([term for (term, _) in wv.most_similar(docs_mean_vector)])
            f.write(f'<hr/><b>Cluster {label} ({len(docs)} docs)</b><hr/>')
            f.write(f'<i>{terms}</i><hr/>')
            for doc in docs:
                row = docs_df.iloc[doc]
                f.write(f'<a target="_blank" href="{row.url}">{row.pgpid}</a><br/>')
                f.write('Tags: <i>' + str(row.tags) + '</i>')
                if row['is_exemplar']:
                    f.write('<p style="color:red;">' + str(row.description) + '</p>')
                else:
                    f.write('<p>' + str(row.description) + '</p>')


if __name__ == '__main__':

    logging.basicConfig(level=os.environ.get('LOGLEVEL', 'INFO'))
    sns.set()

    # ----------- Copy script and params -------------- #
    existing_runs = sorted([d for d in os.listdir('results') if os.path.isdir(f'results/{d}')])
    if existing_runs:
        run_id = int(existing_runs[-1]) + 1
    else:
        run_id = 1
    run_id = f'{run_id:04}'

    output_dir = os.path.join('results', run_id)
    os.makedirs(output_dir, exist_ok=True)
    logger.addHandler(logging.FileHandler(os.path.join(output_dir, 'log.txt')))
    shutil.copy(__file__, output_dir)
    with open(os.path.join(output_dir, 'params.txt'), 'w') as f:
        pprint(PARAMS, f)

    _stop_words = []
    os.makedirs(f'{output_dir}/stopwords', exist_ok=True)
    for filename in glob('stopwords/*.txt'):
        _stop_words.extend([l.lower() for l in open(filename, 'r').read().splitlines() if l.strip()
                            and not l.startswith('#')])
        shutil.copy(filename, os.path.join(output_dir, filename))
    # ----------- Copy script and params -------------- #

    stop_words = _stop_words + nltk.corpus.stopwords.words('english')  # nltk.download('stopwords')

    df = pd.read_csv('data.csv', dtype={'tags': str})[:PARAMS['MAX_DOCS']]
    logger.info(f'No. of records = {len(df)}')
    df = df.dropna(subset=['description'])
    logger.info(f'After dropping records with missing description, no. of records = {len(df)}')
    df['tags'] = df['tags'].str.lower()
    df['tags'].fillna('', inplace=True)

    # -------------- Add additional columns to Dataframe --------------- #
    df['preference'] = 0
    df['is_exemplar'] = False
    # -------------- Add additional columns to Dataframe --------------- #

    # -------------- Find common descriptions ----------- #
    descriptions = Counter()
    for i, row in df.iterrows():
        descriptions.update([row.description])
    common_descriptions = [t[0] for t in descriptions.most_common(PARAMS['AFFINITY_PREFERENCE_N_DESCRIPTIONS'])]
    # -------------- Find common descriptions ----------- #

    # -------------- Find common tags --------------- #
    tags = Counter()
    tag_dict = {}
    for i, row in df.iterrows():
        try:
            _tags = row.tags.split(',')
        except:
            continue
        else:
            for tag in _tags:
                tag = tag.strip().lower().replace(':', '').replace('.', '').replace(';', '').replace('(', '').replace(')', '')
                if tag not in PARAMS['AFFINITY_PREFERENCE_BAD_TAGS']:
                    tags.update([tag])

    common_tags = [t[0] for t in tags.most_common(PARAMS['AFFINITY_PREFERENCE_N_TAGS'])]
    # -------------- Find common tags --------------- #

    data_pkl_file = os.path.join(output_dir, 'data.pik')
    if not os.path.exists(data_pkl_file):
        data = list(df.description)
        data = process_words(data, stop_words=stop_words, disallowed_ners=PARAMS['DISALLOWED_NERS'],
                             min_len=PARAMS['MIN_LEN'], max_len=PARAMS['MAX_LEN'])
        logger.info(f'After filtering stopwords/short words/lemmatization, no. of records = {len(data)}')

        with open(data_pkl_file, 'wb') as f:
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
    else:
        with open(data_pkl_file, 'rb') as f:
            data = pickle.load(f)

    if not os.path.exists(os.path.join(output_dir, 'wvmodel.bin')):
        model = Word2Vec(
            sentences=data,
            vector_size=PARAMS['WORD2VEC_VECTOR_SIZE'],
            workers=8,
            sg=1,
            window=PARAMS['WORD2VEC_WINDOW'],
            epochs=PARAMS['WORD2VEC_EPOCHS']
        )
        model.save(os.path.join(output_dir, 'wvmodel.bin'))
        with open(os.path.join(output_dir, 'wvmodel_keys.txt'), 'w') as f:
            f.write('\n'.join(model.wv.index_to_key))
    else:
        model = Word2Vec.load(os.path.join(output_dir, 'wvmodel.bin'))

    wv = model.wv
    # # wv = api.load('word2vec-google-news-300')  # pre-trained model
    # plot_word2vec_model(model)

    # print(wv.most_similar('father', topn=20))

    n_docs = PARAMS['AFFINITY_N_DOCS']
    X = vectorize(data[:n_docs], model=model)
    logger.info(f'Vectorization of {n_docs} documents done.')

    logger.info('Fitting AffinityPropagation model to documents..')
    af = AffinityPropagation(verbose=True, damping=PARAMS['AFFINITY_DAMPING']).fit(X)
    generate_html(df, wv, af, X, output_dir, 'affinity_clustering.html')
    generate_cluster_size_figure(af=af, output_dir=output_dir, filename='affinity_clustering.png')

    # If we didn't specify starting preference values, it would have been the median (for all data points):
    median_preference = np.median(af.affinity_matrix_)
    logger.info(f'Median Preference Value of AF model: {median_preference}')
    min_preference = np.min(af.affinity_matrix_)
    logger.info(f'Min Preference Value of AF model: {min_preference}')
    max_preference = np.max(af.affinity_matrix_)
    logger.info(f'Max Preference Value of AF model: {max_preference}')

    exemplar_preference = max_preference
    df['preference'] = median_preference

    for common_tag in common_tags:
        matching_indices = np.where(df.tags.str.contains(common_tag))[0]
        if len(matching_indices) > 0:
            randomly_selected_doc_index = np.random.choice(matching_indices, 1)[0]
            df.at[randomly_selected_doc_index, 'preference'] = exemplar_preference
            df.at[randomly_selected_doc_index, 'is_exemplar'] = True

    for common_description in common_descriptions:
        matching_indices = np.where(df.description == common_description)[0]
        if len(matching_indices) > 0:
            randomly_selected_doc_index = np.random.choice(matching_indices, 1)[0]
            df.at[randomly_selected_doc_index, 'preference'] = exemplar_preference
            df.at[randomly_selected_doc_index, 'is_exemplar'] = True

    logger.info(f'Total no. of exemplars set = {len(df[df.is_exemplar==True])}')
    logger.info(f'Recreating AffinityPropagation after setting preference={exemplar_preference} for exemplars')

    af = AffinityPropagation(
        verbose=True,
        preference=df['preference'].to_numpy(),
        damping=PARAMS['AFFINITY_DAMPING']
    ).fit(X)

    generate_html(df, wv, af, X, output_dir, 'affinity_clustering_with_preferences.html')
    generate_cluster_size_figure(af=af, output_dir=output_dir, filename='affinity_clustering_with_preferences.png')

    # coeff = metrics.silhouette_score(X, labels, metric='sqeuclidean')
    # logger.info(f'Silhouette Coefficient: {coeff}')

    # plt.close('all')
    # plt.figure(1)
    # plt.clf()
    #
    # colors = cycle('bgrcmykbgrcmykbgrcmykbgrcmyk')
    # for k, col in zip(range(n_clusters_), colors):
    #     class_members = labels == k
    #     cluster_center = X[cluster_centers_indices[k]]
    #     plt.plot(X[class_members, 0], X[class_members, 1], col + '.')
    #     plt.plot(
    #         cluster_center[0],
    #         cluster_center[1],
    #         'o',
    #         markerfacecolor=col,
    #         markeredgecolor='k',
    #         markersize=14,
    #     )
    #     for x in X[class_members]:
    #         plt.plot([cluster_center[0], x[0]], [cluster_center[1], x[1]], col)
    #
    # plt.title(f'Estimated number of clusters: {n_clusters_}')
    # plt.savefig(os.path.join(output_dir, 'clusters.png'))
