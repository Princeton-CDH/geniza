import os.path
from collections import Counter
import numpy as np
import matplotlib.pyplot as plt


def generate_cluster_size_figure(filename, output_dir=None, af=None, results_html_filepath=None):
    assert any([af, results_html_filepath]) and not all([af, results_html_filepath])
    if output_dir is None:
        assert results_html_filepath is not None
        output_dir = os.path.dirname(results_html_filepath)

    if results_html_filepath is not None:
        s = open(results_html_filepath, 'r').read()
        tokens = s.split('<hr/>')
        cluster_counts = []
        for i, token in enumerate(tokens):
            if token.startswith('<b>Cluster '):
                _start_pos = token.index('(')
                _end_pos = token.index('docs')
                n = int(token[_start_pos+1:_end_pos])
                cluster_counts.append(n)

    else:
        counts = dict(Counter(af.labels_))
        cluster_counts = [0] * len(af.labels_)
        for k, v in counts.items():
            cluster_counts[k] = v

    cluster_counts = np.array(cluster_counts)
    plt.hist(cluster_counts)
    plt.savefig(os.path.join(output_dir, filename))
    plt.clf()


if __name__ == '__main__':
    generate_cluster_size_figure(
        filename='affinity_clustering_with_preferences.png',
        results_html_filepath='results/0086/affinity_clustering_with_preferences.html'
    )