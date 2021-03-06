import os
import unittest
import numpy as np

from Orange.data import Table
from Orange.data.domain import Domain, StringVariable

from orangecontrib.text.corpus import Corpus


class CorpusTests(unittest.TestCase):
    def test_corpus_from_file(self):
        c = Corpus.from_file('bookexcerpts')
        self.assertEqual(len(c), 140)
        self.assertEqual(len(c.domain), 1)
        self.assertEqual(len(c.domain.metas), 1)
        self.assertEqual(c.metas.shape, (140, 1))

        c = Corpus.from_file('deerwester')
        self.assertEqual(len(c), 9)
        self.assertEqual(len(c.domain), 1)
        self.assertEqual(len(c.domain.metas), 1)
        self.assertEqual(c.metas.shape, (9, 1))

    def test_corpus_from_file_abs_path(self):
        c = Corpus.from_file('bookexcerpts')
        path = os.path.dirname(__file__)
        file = os.path.abspath(os.path.join(path, '..', 'datasets', 'bookexcerpts.tab'))
        c2 = Corpus.from_file(file)
        self.assertEqual(c, c2)

    def test_corpus_from_file_with_tab(self):
        c = Corpus.from_file('bookexcerpts')
        c2 = Corpus.from_file('bookexcerpts.tab')
        self.assertEqual(c, c2)

    def test_corpus_from_file_missing(self):
        with self.assertRaises(FileNotFoundError):
            Corpus.from_file('missing_file')

    def test_corpus_from_init(self):
        c = Corpus.from_file('bookexcerpts')
        c2 = Corpus(c.X, c.Y, c.metas, c.domain, c.text_features)
        self.assertEqual(c, c2)

    def test_extend_corpus(self):
        c = Corpus.from_file('bookexcerpts')
        n_classes = len(c.domain.class_var.values)
        c_copy = c.copy()
        new_y = [c.domain.class_var.values[int(i)] for i in c.Y]
        new_y[0] = 'teenager'
        c.extend_corpus(c.metas, new_y)

        self.assertEqual(len(c), len(c_copy)*2)
        self.assertEqual(c.Y.shape[0], c_copy.Y.shape[0]*2)
        self.assertEqual(c.metas.shape[0], c_copy.metas.shape[0]*2)
        self.assertEqual(c.metas.shape[1], c_copy.metas.shape[1])
        self.assertEqual(len(c_copy.domain.class_var.values), n_classes+1)

    def test_corpus_not_eq(self):
        c = Corpus.from_file('bookexcerpts')
        n_doc = c.X.shape[0]

        c2 = Corpus(c.X, c.Y, c.metas, c.domain, [])
        self.assertNotEqual(c, c2)

        c2 = Corpus(np.ones((n_doc, 1)), c.Y, c.metas, c.domain, c.text_features)
        self.assertNotEqual(c, c2)

        c2 = Corpus(c.X, np.ones((n_doc, 1)), c.metas, c.domain, c.text_features)
        self.assertNotEqual(c, c2)

        broken_metas = np.copy(c.metas)
        broken_metas[0, 0] = ''
        c2 = Corpus(c.X, c.Y, broken_metas, c.domain, c.text_features)
        self.assertNotEqual(c, c2)

        new_meta = [StringVariable('text2')]
        broken_domain = Domain(c.domain.attributes, c.domain.class_var, new_meta)
        c2 = Corpus(c.X, c.Y, c.metas, broken_domain, new_meta)
        self.assertNotEqual(c, c2)

    def test_from_table(self):
        t = Table.from_file('brown-selected')
        self.assertIsInstance(t, Table)

        c = Corpus.from_table(t.domain, t)
        self.assertIsInstance(c, Corpus)
        self.assertEqual(len(t), len(c))
        np.testing.assert_equal(t.metas, c.metas)
        self.assertEqual(c.text_features, [t.domain.metas[0]])

    def test_from_corpus(self):
        c = Corpus.from_file('bookexcerpts')
        c2 = Corpus.from_corpus(c.domain, c, row_indices=list(range(5)))
        self.assertEqual(len(c2), 5)

    def test_infer_text_features(self):
        c = Corpus.from_file('friends-transcripts')
        tf = c.text_features
        self.assertEqual(len(tf), 1)
        self.assertEqual(tf[0].name, 'Quote')

        c = Corpus.from_file('deerwester')
        tf = c.text_features
        self.assertEqual(len(tf), 1)
        self.assertEqual(tf[0].name, 'text')

    def test_asserting_errors(self):
        c = Corpus.from_file('bookexcerpts')

        with self.assertRaises(TypeError):
            Corpus(1.0, c.Y, c.metas, c.domain, c.text_features)

        too_large_x = np.vstack((c.X, c.X))
        with self.assertRaises(ValueError):
            Corpus(too_large_x, c.Y, c.metas, c.domain, c.text_features)

        with self.assertRaises(ValueError):
            c.set_text_features([StringVariable('foobar')])

        with self.assertRaises(ValueError):
            c.set_text_features([c.domain.metas[0], c.domain.metas[0]])
