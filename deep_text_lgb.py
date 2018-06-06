import gc

import pandas as pd

from scipy.sparse import hstack, csr_matrix

from sklearn.feature_selection.univariate_selection import SelectKBest, f_regression

import lightgbm as lgb

from cv import run_cv_model
from utils import print_step, rmse, bin_and_ohe_data
from cache import get_data, is_in_cache, load_cache, save_in_cache


# LGB Model Definition
def runLGB(train_X, train_y, test_X, test_y, test_X2):
    d_train = lgb.Dataset(train_X, label=train_y)
    d_valid = lgb.Dataset(test_X, label=test_y)
    watchlist = [d_train, d_valid]
    params = {'learning_rate': 0.1,
              'application': 'regression',
              'max_depth': 9,
              'num_leaves': 2 ** 9,
              'verbosity': -1,
              'metric': 'rmse',
              'data_random_seed': 3,
              'bagging_fraction': 0.8,
              'feature_fraction': 0.2,
              'nthread': 3,
              'lambda_l1': 1,
              'lambda_l2': 1,
              'min_data_in_leaf': 40}
    model = lgb.train(params,
                      train_set=d_train,
                      num_boost_round=1000,
                      valid_sets=watchlist,
                      verbose_eval=10)
    print_step('Predict 1/2')
    pred_test_y = model.predict(test_X)
    print_step('Predict 2/2')
    pred_test_y2 = model.predict(test_X2)
    return pred_test_y, pred_test_y2


print('~~~~~~~~~~~~~~~~~~~~~~~')
print_step('Importing Data 1/6')
train, test = get_data()

print('~~~~~~~~~~~~~~~')
print_step('Subsetting')
target = train['deal_probability']
train_id = train['item_id']
test_id = test['item_id']
train.drop(['deal_probability', 'item_id'], axis=1, inplace=True)
test.drop(['item_id'], axis=1, inplace=True)

if not is_in_cache('deep_text_feats'):
    print('~~~~~~~~~~~~~~~~~~~~~~~')
    print_step('Importing Data 2/6')
    tfidf_train, tfidf_test = load_cache('titlecat_tfidf')

    print_step('Importing Data 3/6')
    tfidf_train2, tfidf_test2 = load_cache('text_tfidf')

    print_step('Importing Data 4/6')
    tfidf_train3, tfidf_test3 = load_cache('text_char_tfidf')


    print_step('Importing Data 5/6')
    train = hstack((tfidf_train, tfidf_train2, tfidf_train3)).tocsr()
    print_step('Importing Data 6/6')
    test = hstack((tfidf_test, tfidf_test2, tfidf_test3)).tocsr()
    print(train.shape)
    print(test.shape)

    print_step('SelectKBest 1/2')
    fselect = SelectKBest(f_regression, k=40000)
    train = fselect.fit_transform(train, target)
    print_step('SelectKBest 2/2')
    test = fselect.transform(test)
    print(train.shape)
    print(test.shape)

    print_step('GC')
    del tfidf_test
    del tfidf_test2
    del tfidf_test3
    del tfidf_train
    del tfidf_train2
    del tfidf_train3
    gc.collect()

    print_step('Importing Data 7/7')
    train_fe, test_fe = load_cache('data_with_fe')
    dummy_cols = ['parent_category_name', 'category_name', 'user_type', 'image_top_1',
                  'day_of_week', 'region', 'city', 'param_1', 'param_2', 'param_3', 'cat_bin']
    numeric_cols = ['price', 'num_words_description', 'num_words_title', 'num_chars_description',
                    'num_chars_title', 'num_capital_description', 'num_capital_title', 'num_lowercase_title',
                    'capital_per_char_description', 'capital_per_char_title', 'num_punctuations_description',
                    'punctuation_per_char_description', 'punctuation_per_char_title', 'num_words_upper_description',
                    'num_words_lower_description', 'num_words_entitled_description', 'chars_per_word_description',
                    'chars_per_word_title', 'description_words_per_title_words', 'description_chars_per_title_chars',
                    'num_english_chars_description', 'num_english_chars_title', 'english_chars_per_char_description',
                    'english_chars_per_char_title', 'num_english_words_description', 'english_words_per_word_description',
                    'max_word_length_description', 'max_word_length_title', 'mean_word_length_description', 'mean_word_length_title',
                    'num_stopwords_description', 'number_count_description', 'number_count_title', 'num_unique_words_description',
                    'unique_words_per_word_description', 'item_seq_number', 'adjusted_seq_num', 'user_num_days', 'user_days_range',
                    'cat_price_mean', 'cat_price_diff', 'parent_cat_count', 'region_X_cat_count', 'city_count',
                    'num_lowercase_description', 'num_punctuations_title', 'sentence_mean', 'sentence_std',
                    'words_per_sentence', 'price_missing']

    print_step('Importing Data 8/5 1/5')
    train_img, test_img = load_cache('img_data')
    print_step('Importing Data 8/5 2/5')
    drops = ['item_id', 'img_path', 'img_std_color', 'img_sum_color', 'img_rms_color',
             'img_var_color', 'img_average_color', 'deal_probability']
    drops += [c for c in train_img if 'hist' in c]
    img_dummy_cols = ['img_average_color']
    img_numeric_cols = list(set(train_img.columns) - set(drops) - set(dummy_cols))
    train_img = train_img[img_numeric_cols + img_dummy_cols].fillna(0)
    test_img = test_img[img_numeric_cols + img_dummy_cols].fillna(0)
    dummy_cols += img_dummy_cols
    numeric_cols += img_numeric_cols

    print_step('Importing Data 9/5 2/8')
# HT: https://www.kaggle.com/jpmiller/russian-cities/data
# HT: https://www.kaggle.com/jpmiller/exploring-geography-for-1-5m-deals/notebook
    locations = pd.read_csv('city_latlons.csv')
    print_step('Importing Data 9/5 3/8')
    train_fe = train_fe.merge(locations, how='left', left_on='city', right_on='location')
    print_step('Importing Data 9/5 4/8')
    test_fe = test_fe.merge(locations, how='left', left_on='city', right_on='location')
    numeric_cols += ['lat', 'lon']

    print_step('Importing Data 10/5 2/8')
    region_macro = pd.read_csv('region_macro.csv')
    print_step('Importing Data 10/5 3/8')
    train_fe = train_fe.merge(region_macro, how='left', on='region')
    print_step('Importing Data 10/5 4/8')
    test_fe = test_fe.merge(region_macro, how='left', on='region')
    numeric_cols += ['unemployment_rate', 'GDP_PC_PPP', 'HDI']

    print_step('Importing Data 11/5 1/4')
    train_active, test_active = load_cache('active_feats')
    train_active.fillna(0, inplace=True)
    test_active.fillna(0, inplace=True)
    train_active.drop('user_id', axis=1, inplace=True)
    test_active.drop('user_id', axis=1, inplace=True)
    numeric_cols += train_active.columns.values.tolist()

    print_step('CSR 1/7')
    train_ = pd.concat([train_fe, train_img, train_active], axis=1)
    print_step('CSR 2/7')
    test_ = pd.concat([test_fe, test_img, test_active], axis=1)
    print_step('CSR 3/7')
    train_ohe = csr_matrix(train_[numeric_cols])
    print_step('CSR 4/7')
    test_ohe = csr_matrix(test_[numeric_cols])
    print_step('CSR 5/7')
    train_ohe2, test_ohe2 = bin_and_ohe_data(train_, test_, numeric_cols=[], dummy_cols=dummy_cols)
    print_step('CSR 6/7')
    train = hstack((train, train_ohe, train_ohe2)).tocsr()
    print(train.shape)
    print_step('CSR 7/7')
    test = hstack((test, test_ohe, test_ohe2)).tocsr()
    print(test.shape)

    print_step('GC')
    del train_fe
    del test_fe
    del train_img
    del test_img
    del train_active
    del test_active
    del train_
    del test_
    del test_ohe
    del test_ohe2
    del train_ohe
    del train_ohe2
    gc.collect()

    print_step('Caching')
    save_in_cache('deep_text_feats', train, test)
else:
    train, test = load_cache('deep_text_feats')


print('~~~~~~~~~~~~')
print_step('Run LGB')
results = run_cv_model(train, test, target, runLGB, rmse, 'lgb')
import pdb
pdb.set_trace()

print('~~~~~~~~~~')
print_step('Cache')
save_in_cache('deep_text_lgb', pd.DataFrame({'deep_text_lgb': results['train']}),
                               pd.DataFrame({'deep_text_lgb': results['test']}))

print('~~~~~~~~~~~~~~~~~~~~~~~~~~~~~')
print_step('Prepping submission file')
submission = pd.DataFrame()
submission['item_id'] = test_id
submission['deal_probability'] = results['test'].clip(0.0, 1.0)
submission.to_csv('submit/submit_lgb7.csv', index=False)
print_step('Done!')

# Deep LGB                                                       - Dim 195673, 5CV 0.22196

# CURRENT
# [2018-05-03 09:16:12.670379] lgb cv scores : [0.22257689498410263, 0.22140350676341775, 0.22190683421601698, 0.22168666577421173, 0.22221717818648018]
# [2018-05-03 09:16:12.671351] lgb mean cv score : 0.22195821598484583
# [2018-05-03 09:16:12.672767] lgb std cv score : 0.00040838879744612577

# [10]    training's rmse: 0.240701       valid_1's rmse: 0.241443
# [100]   training's rmse: 0.224196       valid_1's rmse: 0.227253
# [200]   training's rmse: 0.221323       valid_1's rmse: 0.225548
# [300]   training's rmse: 0.21958        valid_1's rmse: 0.224654
# [400]   training's rmse: 0.218335       valid_1's rmse: 0.224104
# [500]   training's rmse: 0.217273       valid_1's rmse: 0.223712
# [600]   training's rmse: 0.216378       valid_1's rmse: 0.223389
# [700]   training's rmse: 0.215555       valid_1's rmse: 0.223133
# [800]   training's rmse: 0.214814       valid_1's rmse: 0.222927
# [900]   training's rmse: 0.21409        valid_1's rmse: 0.222717
# [1000]  training's rmse: 0.213506       valid_1's rmse: 0.222577
