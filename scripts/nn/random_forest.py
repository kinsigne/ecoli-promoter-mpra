# from __future__ import absolute_import, division, print_function
import pandas as pd
import numpy as np, random
np.random.seed(1)
random.seed(1)
from abc import abstractmethod, ABCMeta
# from keras_regression import SequenceDNN, RandomForestRegression, DecisionTree
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier as scikit_DecisionTree
# from hyperparameter_search_regression import HyperparameterSearcher, RandomSearch
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
try:
    from sklearn.model_selection import train_test_split  # sklearn >= 0.18
except ImportError:
    from sklearn.cross_validation import train_test_split  # sklearn < 0.18
import sys
import argparse
import time
import itertools
from collections import Counter
from dragonn_metrics import ClassificationResult


class Model(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, **hyperparameters):
        pass

    @abstractmethod
    def train(self, X, y, validation_data):
        pass

    @abstractmethod
    def predict(self, X):
        pass

    def test(self, X, y):
        return self.score(X, y)

    def score(self, X, y):
        pass


class DecisionTree(Model):

    def __init__(self):
        self.classifier = scikit_DecisionTree()

    def train(self, X, y, validation_data=None):
        self.classifier.fit(X, y)

    def predict(self, X):
        predictions = np.asarray(self.classifier.predict_proba(X))[..., 1]
        if len(predictions.shape) == 2:  # multitask
            predictions = predictions.T
        else:  # single-task
            predictions = np.expand_dims(predictions, 1)
        return predictions


class RandomForestRegression(DecisionTree):

    def __init__(self):
        self.regressor = RandomForestRegressor(n_estimators=100)

    def train(self, X, y, validation_data=None):
        # X shape: n_samples, n_features
        # y shape: n_samples
        self.regressor.fit(X, y)

    def predict(self, X):
        return self.regressor.predict(X)

    def score(self, X, y):
        predictions = np.squeeze(self.regressor.predict(X))
        return np.corrcoef(predictions, y)[0,1]


class RandomForestClassification(DecisionTree):

    def __init__(self):
        self.classifier = RandomForestClassifier(n_estimators=100)

    def train(self, X, y, validation_data=None):
        # X shape: n_samples, n_features
        # y shape: n_samples
        self.classifier.fit(X, y)

    def predict(self, X):
        return self.classifier.predict(X)

    def score(self, X, y):
        return ClassificationResult(y, self.predict(X))


# def one_hot_encode(sequences):
# 	# horizontal one-hot encoding
#     sequence_length = len(sequences[0])
#     integer_type = np.int8 if sys.version_info[
#         0] == 2 else np.int32  # depends on Python version
#     integer_array = LabelEncoder().fit(np.array(('ACGTN',)).view(integer_type)).transform(
#         sequences.view(integer_type)).reshape(len(sequences), sequence_length)
#     one_hot_encoding = OneHotEncoder(
#         sparse=False, n_values=5, dtype=integer_type).fit_transform(integer_array)

#     return one_hot_encoding.reshape(
#         len(sequences), 1, sequence_length, 5).swapaxes(2, 3)[:, :, [0, 1, 2, 4], :]


def one_hot_encode_2d(sequences):
	# horizontal one-hot encoding
    sequence_length = len(sequences[0])
    integer_type = np.int8 if sys.version_info[
        0] == 2 else np.int32  # depends on Python version
    integer_array = LabelEncoder().fit(np.array(('ACGTN',)).view(integer_type)).transform(
        sequences.view(integer_type)).reshape(len(sequences), sequence_length)
    one_hot_encoding = OneHotEncoder(
        sparse=False, n_values=5, dtype=integer_type).fit_transform(integer_array)
    # dimensions are n-samples, n-features. The one hot encoded vector is kept as a single
    # vector instead of split into 1x4 matrix. n-features = 4 * sequence_length
    return one_hot_encoding


def pad_sequence(seq, max_length):
	if len(seq) > max_length:
		diff = len(seq) - max_length
		# diff%2 returns 1 if odd
		trim_length = int(diff / 2)
		seq = seq[trim_length : -(trim_length + diff%2)]
	else:
		seq = seq.center(max_length, 'N')

	return seq


def process_seqs_onehot(filename, seq_length, encode_type='1d'):

	seqs = fasta_reader(filename)
	padded_seqs = [pad_sequence(x, seq_length) for x in seqs]
	if encode_type == '1d':
		X = one_hot_encode(np.array(padded_seqs))
	elif encode_type == '2d':
		# only keep 150bp sequences
		X = one_hot_encode_2d(np.array([x for x in padded_seqs]))
	else:
		raise ValueException('Non-valid encoding type')

	y = np.array([float(line.strip().split('\t')[1]) for line in open(filename)])
	return X, y



def process_seqs(filename):

	data = pd.read_table(filename, header=None)
	sequences = data.loc[:, 0]
	y = np.array(data.loc[:, 1])
	X = np.array(data.loc[:, 2:])
	
	return X, y


if __name__ == '__main__':

	parser = argparse.ArgumentParser()
	parser.add_argument('train', help='''Training set. If one-hot encoded DNA, one
		column for sequence, one for expression. If features: first column sequence, 
		second column expression, remaining columns are features.''')
	parser.add_argument('test', help='''Test sest. Same format as training set.''')
	parser.add_argument('output_name')
	parser.add_argument('--onehot', action='store_true', help='''If feature is raw DNA
		sequence and should be one-hot encoded''')
	parser.add_argument('--seq_length', type=int, help='sequence length, needed for one-hot encoding')
	parser.add_argument('--classification', action='store_true',
		help='Run random forest classification')
	parser.add_argument('--regression', action='store_true',
		help='Run random forest regression')
	args = parser.parse_args()

	# load in pre-defined splits
	print("loading training and test set...")
	if args.onehot:
		X_train, y_train = process_seqs_onehot(args.train, args.seq_length, '2d')
		X_test, y_test = process_seqs_onehot(args.test, args.seq_length, '2d')
	else:
		X_train, y_train = process_seqs(args.train)
		X_test, y_test = process_seqs(args.test)


	if args.regression:
		print("Running random forest regression...")
		model = RandomForestRegression()
		model.train(X_train, y_train)
		predictions = model.predict(X_test)

	if args.classification:
		print("Running random forest classification...")
		model = RandomForestClassification()
		model.train(X_train, y_train)
		predictions = model.predict(X_test)


	with open(args.output_name, 'w') as outfile:
		for i in range(len(predictions)):
			outfile.write(str(float(predictions[i])) + '\t' +
				      str(float(y_test[i])) + '\n')

	score = model.score(X_test, y_test)
	print("Score:", score)

