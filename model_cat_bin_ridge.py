# HT: https://www.kaggle.com/domcastro/version-24/code

import pandas as pd
import numpy as np

import pathos.multiprocessing as mp

from scipy.sparse import hstack

from sklearn.feature_extraction.text import TfidfVectorizer

from sklearn.linear_model import Ridge

from cv import run_cv_model
from utils import rmse, normalize_text, print_step
from cache import get_data, is_in_cache, load_cache, save_in_cache


def runRidge(train_X, train_y, test_X, test_y, test_X2, params):
    model = Ridge(**params)
    print_step('Fit Ridge')
    model.fit(train_X, train_y)
    print_step('Ridge Predict 1/2')
    pred_test_y = model.predict(test_X)
    print_step('Ridge Predict 2/2')
    pred_test_y2 = model.predict(test_X2)
    return pred_test_y, pred_test_y2

print('~~~~~~~~~~~~~~~~~~~')
print_step('Importing Data')
train, test = get_data()

print('~~~~~~~~~~~~')
print_step('Merging')
merge = pd.concat([train, test])

print('~~~~~~~~~~~~~~~~')
print_step('Cat Bin 1/5')
merge['cat_bin'] = (merge['category_name'] + merge['param_1'].fillna('') + merge['param_2'].fillna('') + merge['param_3'].fillna(''))
merge['cat_bin_count'] = merge.groupby('cat_bin')['cat_bin'].transform('count')
print_step('Cat Bin 2/5')
merge.loc[merge['cat_bin_count'] < 300, 'cat_bin'] = (merge.loc[merge['cat_bin_count'] < 300, 'category_name'] + merge.loc[merge['cat_bin_count'] < 300, 'param_1'].fillna('') + merge.loc[merge['cat_bin_count'] < 300, 'param_2'].fillna(''))
merge['cat_bin_count'] = merge.groupby('cat_bin')['cat_bin'].transform('count')
print_step('Cat Bin 3/5')
merge.loc[merge['cat_bin_count'] < 300, 'cat_bin'] = (merge.loc[merge['cat_bin_count'] < 300, 'category_name'] + merge.loc[merge['cat_bin_count'] < 300, 'param_1'].fillna(''))
merge['cat_bin_count'] = merge.groupby('cat_bin')['cat_bin'].transform('count')
print_step('Cat Bin 4/5')
merge.loc[merge['cat_bin_count'] < 300, 'cat_bin'] = merge.loc[merge['cat_bin_count'] < 300, 'category_name']
merge['cat_bin_count'] = merge.groupby('cat_bin')['cat_bin'].transform('count')
print_step('Cat Bin 5/5')
merge.loc[merge['cat_bin_count'] < 300, 'cat_bin'] = merge.loc[merge['cat_bin_count'] < 300, 'category_name']
merge.drop('cat_bin_count', axis=1, inplace=True)
merge['cat_bin'] = merge['cat_bin'].apply(lambda s: s.replace('/', '-'))

print('~~~~~~~~~~~~')
print_step('Unmerge')
dim = train.shape[0]
train = pd.DataFrame(merge.values[:dim, :], columns = merge.columns)
test = pd.DataFrame(merge.values[dim:, :], columns = merge.columns)
print(train.shape)
print(test.shape)


def run_ridge_on_cat_bin(cat_bin):
    if not is_in_cache('cat_bin_ridges_' + cat_bin):
        print_step(cat_bin + ' > Subsetting')
        train_c = train[train['cat_bin'] == cat_bin].copy()
        test_c = test[test['cat_bin'] == cat_bin].copy()
        print(train_c.shape)
        print(test_c.shape)
        target = train_c['deal_probability'].values
        train_id = train_c['item_id']
        test_id = test_c['item_id']
        train_c.drop(['deal_probability', 'item_id'], axis=1, inplace=True)
        test_c.drop(['item_id'], axis=1, inplace=True)

        print_step(cat_bin + ' > Titlecat TFIDF 1/3')
        train_c['titlecat'] = train_c['category_name'].fillna('') + ' ' + train_c['param_1'].fillna('') + ' ' + train_c['param_2'].fillna('') + ' ' + train_c['param_3'].fillna('') + ' ' + train_c['title'].fillna('')
        test_c['titlecat'] = test_c['category_name'].fillna('') + ' ' + test_c['param_1'].fillna('') + ' ' + test_c['param_2'].fillna('') + ' ' + test_c['param_3'].fillna('') + ' ' + test_c['title'].fillna('')
        print_step(cat_bin + ' > Titlecat TFIDF 2/3')
        tfidf = TfidfVectorizer(ngram_range=(1, 2),
                                max_features=50000,
                                binary=True,
                                encoding='KOI8-R')
        tfidf_train = tfidf.fit_transform(train_c['titlecat'])
        print(tfidf_train.shape)
        print_step(cat_bin + ' > Titlecat TFIDF 3/3')
        tfidf_test = tfidf.transform(test_c['titlecat'])
        print(tfidf_test.shape)

        print_step(cat_bin + ' > Titlecat TFIDF Ridge')
        results = run_cv_model(tfidf_train, tfidf_test, target, runRidge, {'alpha': 5.0}, rmse, cat_bin + '-titlecat-ridge')
        train_c['cat_bin_title_ridge'] = results['train']
        test_c['cat_bin_title_ridge'] = results['test']

        print_step(cat_bin + ' > Description TFIDF 1/3')
        train_c['desc'] = train_c['title'].fillna('') + ' ' + train_c['description'].fillna('')
        test_c['desc'] = test_c['title'].fillna('') + ' ' + test_c['description'].fillna('')
        print_step(cat_bin + ' > Description TFIDF 2/3')
        tfidf = TfidfVectorizer(ngram_range=(1, 2),
                                max_features=50000,
                                binary=True,
                                encoding='KOI8-R')
        tfidf_train2 = tfidf.fit_transform(train_c['desc'].fillna(''))
        print(tfidf_train2.shape)
        print_step(cat_bin + ' > Description TFIDF 3/3')
        tfidf_test2 = tfidf.transform(test_c['desc'].fillna(''))
        print(tfidf_test2.shape)
        results = run_cv_model(tfidf_train2, tfidf_test2, target, runRidge, {'alpha': 5.0}, rmse, cat_bin + '-desc-ridge')
        train_c['cat_bin_desc_ridge'] = results['train']
        test_c['cat_bin_desc_ridge'] = results['test']

        print_step(cat_bin + ' > Text Char TFIDF 1/2')
        # Using char n-grams ends up being surprisingly good, HT https://www.kaggle.com/c/avito-demand-prediction/discussion/56061#325063
        tfidf = TfidfVectorizer(ngram_range=(2, 5),
                                max_features=50000,
                                binary=True,
                                analyzer='char',
                                encoding='KOI8-R')
        tfidf_train3 = tfidf.fit_transform(train_c['desc'])
        print(tfidf_train3.shape)
        print_step(cat_bin + ' > Text Char TFIDF 2/2')
        tfidf_test3 = tfidf.transform(test_c['desc'])
        print(tfidf_test3.shape)

        results = run_cv_model(tfidf_train3, tfidf_test3, target, runRidge, {'alpha': 5.0}, rmse, cat_bin + '-desc-char-ridge')
        train_c['cat_bin_desc_char_ridge'] = results['train']
        test_c['cat_bin_desc_char_ridge'] = results['test']

        print_step('Merging 1/2')
        train_c2 = hstack((tfidf_train, tfidf_train2, tfidf_train3)).tocsr()
        print_step('Merging 2/2')
        test_c2 = hstack((tfidf_test, tfidf_test2, tfidf_test3)).tocsr()
        print(train_c2.shape)
        print(test_c2.shape)

        print('~~~~~~~~~~~~~~~~~~~~~~~~')
        print_step('Run Full Text Ridge')
        results = run_cv_model(train_c2, test_c2, target, runRidge, {'alpha': 8.0}, rmse, cat_bin + '-text-ridge')
        train_c['cat_bin_all_text_ridge'] = results['train']
        test_c['cat_bin_all_text_ridge'] = results['test']

        print('~~~~~~~~~~~~~~~~~~~~~~')
        print_step(cat_bin + ' > Dropping')
        train_c.drop([c for c in train_c.columns if 'ridge' not in c], axis=1, inplace=True)
        test_c.drop([c for c in test_c.columns if 'ridge' not in c], axis=1, inplace=True)
        train_c['item_id'] = train_id
        test_c['item_id'] = test_id

        print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
        print_step(cat_bin + ' > Saving in Cache')
        save_in_cache('cat_bin_ridges_' + cat_bin, train_c, test_c)
    else:
        print(cat_bin + ' already in cache! Skipping...')
    return True

cat_bins = list(map(lambda s: s.replace('/', '-'), list(set(train['cat_bin'].values))))
n_cpu = mp.cpu_count()
n_nodes = max(n_cpu - 3, 2)
print('Starting a jobs server with %d nodes' % n_nodes)
pool = mp.ProcessingPool(n_nodes, maxtasksperchild=500)
res = pool.map(run_ridge_on_cat_bin, cat_bins)
pool.close()
pool.join()
pool.terminate()
pool.restart()

print('~~~~~~~~~~~~~~~~')
print_step('Merging 1/5')
pool = mp.ProcessingPool(n_nodes, maxtasksperchild=500)
dfs = pool.map(lambda c: load_cache('cat_bin_ridges_' + c), cat_bins)
pool.close()
pool.join()
pool.terminate()
pool.restart()
print_step('Merging 2/5')
train_dfs = map(lambda x: x[0], dfs)
test_dfs = map(lambda x: x[1], dfs)
print_step('Merging 3/5')
train_df = pd.concat(train_dfs)
test_df = pd.concat(test_dfs)
print_step('Merging 4/5')
train_ridge = train.merge(train_df, on='item_id')
print_step('Merging 5/5')
test_ridge = test.merge(test_df, on='item_id')

print_step('RMSEs')
print(rmse(train_ridge['deal_probability'], train_ridge['cat_bin_title_ridge']))
print(rmse(train_ridge['deal_probability'], train_ridge['cat_bin_desc_ridge']))
print(rmse(train_ridge['deal_probability'], train_ridge['cat_bin_desc_char_ridge']))
print(rmse(train_ridge['deal_probability'], train_ridge['cat_bin_all_text_ridge']))
import pdb
pdb.set_trace()

print('~~~~~~~~~~~~~~~')
print_step('Caching...')
save_in_cache('cat_bin_ridges', train_ridge, test_ridge)
