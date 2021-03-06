import json
import os
import re
from collections import Counter

import numpy as np
from nltk.corpus import wordnet as wn
from Adjective_Categories import ADJ_categories, ADJ_suffix
from Adverb_Categories import ADV_categories, ADV_suffix

import spacy
import stanza


'''
Stanza documentation - https://stanfordnlp.github.io/stanza/index.html
UPOS documentation - https://universaldependencies.org/u/pos/
'''
stanza.download('en')
nlp_tagger = stanza.Pipeline(lang='en', processors='tokenize,mwt,pos')
nlp_sim = spacy.load('en_core_web_md')

with_xpos = False
chosen_tags = ['ADJ', 'ADV', 'NOUN', 'VERB']


def get_suffix_tag(word, suffix_dict):
    for key in suffix_dict.keys():
        for suffix in suffix_dict[key]:
            if suffix.findall(word):
                return key
    return 'common'


def get_categorize_tag(word, categories_dict):
    max = 0.
    Tag_syn = nlp_sim(word)
    category_key = 'quantity'
    for i, key in enumerate(categories_dict):
        words = categories_dict[key][:5]
        word_syns = [nlp_sim(word) for word in words]
        similarity_sum = np.sum([Tag_syn.similarity(word_syn) for word_syn in word_syns])
        if similarity_sum > max:
            max = similarity_sum
            category_key = key

    return category_key


def get_last_saved_json(folder, dataset_name):
    listdir = os.listdir(folder)
    regex = re.compile('_(\d+)\.json')
    listdir = [regex.findall(file_name) for file_name in listdir if dataset_name in file_name]
    listdir = [int(file_name[0]) for file_name in listdir if len(file_name) > 0]
    listdir.sort()
    if len(listdir) > 0:
        return int(listdir[-1])
    return 0


def get_extend_tags_tags(dataset, dict_to_json, folder, dataset_name, limit):
    limited_dict = dict()
    sub_categories = dict()
    last_iteration = len(dict_to_json)
    for i, item in dataset.items():
        if (int(i) + last_iteration + 1) % 100 == 0:
            print('Process {}/{}'.format(int(i) + last_iteration + 1, limit))
        dict_to_json[int(i) + last_iteration] = {
            'original': item['original'],
            'class': item['class']
        }
        doc = nlp_tagger(item['original'])
        upos_xpos_lists = (list(), list())
        upos_tuples = [(word.upos, word.text) for sent in doc.sentences for word in sent.words]
        xpos_tuples = [(word.xpos, word.text) for sent in doc.sentences for word in sent.words]

        if with_xpos:
            tagging_tuples = [upos_tuples, xpos_tuples]
        else:
            tagging_tuples = [upos_tuples]
        for j, tag_list in enumerate(tagging_tuples):
            for tag, word in tag_list:
                if tag in ['NOUN', 'ADJ', 'ADV', 'VERB']:
                    if word not in sub_categories or tag not in sub_categories[word]:
                        synsets = wn.synsets(word)
                        synsets = [synset.lexname().replace('noun', 'NOUN').replace('adv', 'ADV')
                                       .replace('verb', 'VERB') for synset in synsets if 'adj' not in synset.lexname()]
                        synsets_counter = Counter(synsets)
                        if tag in ['ADJ', 'ADV']:
                            suffix_tag = get_suffix_tag(word, ADJ_suffix) if tag == 'ADJ' else\
                                get_suffix_tag(word, ADV_suffix)
                            cat_tag = get_categorize_tag(word, ADJ_categories) if tag == 'ADJ' else\
                                get_categorize_tag(word, ADV_categories)
                            sub_categories[word] = {tag: [(cat_tag, 1), (suffix_tag, 1)]}
                        if tag in ['NOUN', 'VERB']:
                            sub_categories[word] = {'NOUN': list(), 'VERB': list()}
                            for synset, incidence in synsets_counter.items():
                                syn_tag, syn_cat = synset.split('.')
                                if syn_tag in ['NOUN', 'VERB']:
                                    sub_categories[word][syn_tag].append((syn_cat, incidence))
                            for syn_tag in ['NOUN', 'VERB']:
                                sorted(sub_categories[word][syn_tag], key=lambda x: x[1], reverse=True)
                    if len(sub_categories[word][tag]) > 0:
                        tag = "_".join([tag] + [cat[0] for cat in sub_categories[word][tag][:2]])

                if j == 0:
                    upos_xpos_lists[0].append(tag)
                else:
                    upos_xpos_lists[1].append(tag)

        dict_to_json[int(i) + last_iteration].update({"upos": " ".join(upos_xpos_lists[0])})
        if with_xpos:
            dict_to_json[int(i) + last_iteration].update({"xpos": " ".join(upos_xpos_lists[1])})

        if (int(i) + last_iteration + 1) % 5000 == 0 or (int(i) + last_iteration + 1) >= limit:
            file_name = folder + '/{}_Dataset_{}.json'.format(dataset_name, int(i) + last_iteration + 1)
            with open(file_name, 'w') as f:
                json.dump(dict_to_json, f)

        if (int(i) + last_iteration + 1) >= limit:
            break

    for i, item in dict_to_json.items():
        if int(i) < limit:
            limited_dict[i] = item
        else:
            break
    return limited_dict


def get_upos_tags(dict_to_json, dataset_name, filter_tags, extend_tags):
    if filter_tags:
        for _, item in dict_to_json.items():
            item['upos'] = " ".join([word for word in item['upos'].split(' ') if len([tag for tag in chosen_tags if tag in word]) > 0])

    if not extend_tags:
        for _, item in dict_to_json.items():
            sent = list()
            for word in item['upos'].split(' '):
                if '_' in word:
                    sent.append(word.split('_')[0])
                else:
                    sent.append(word)
            item['upos'] = " ".join(sent)


def get_bigram_tags(dict_to_json, dataset_name, filter_tags, extend_tags):
    bi_counters_list = [Counter(), Counter()] if dataset_name == 'IMDB' else \
        [Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), Counter()]
    if filter_tags:
        for _, item in dict_to_json.items():
            item['upos'] = " ".join([word for word in item['upos'].split(' ') if len([tag for tag in chosen_tags if tag in word]) > 0])

    for _, item in dict_to_json.items():
        bigram_words = list()
        prev_word = item['upos'].split(' ')[0]
        prev_word = prev_word.split('_')[0] if '_' in prev_word and not extend_tags else prev_word
        for word in item['upos'].split(' ')[1:]:
            word = word.split('_')[0] if '_' in word and not extend_tags else word
            bigram_words.append(prev_word + "#" + word)
            prev_word = word
        bi_counters_list[int(item['class'])].update(Counter(bigram_words))

    for _, item in dict_to_json.items():
        new_phrase = item['upos'].split(' ')
        temp = list()
        for word in new_phrase:
            if '_' in word and not extend_tags:
                temp.append(word.split('_')[0])
            else:
                temp.append(word)
        new_phrase = temp

        times_list = [1 for _ in range(len(new_phrase) - 1)]
        while len(times_list) != 0 and np.sum(times_list) > 0:
            for i in range(len(new_phrase) - 1):
                if '#' not in new_phrase[i] and '#' not in new_phrase[i+1]:
                    times_list[i] = bi_counters_list[int(item['class'])][new_phrase[i] + "#" + new_phrase[i+1]]
                else:
                    times_list[i] = 0
            if np.sum(times_list) == 0:
                break
            idx = np.argmax(times_list)
            new_phrase[idx] = new_phrase[idx] + '#' + new_phrase[idx+1]
            new_phrase.pop(idx + 1), times_list.pop(idx)
        item['upos'] = ' '.join(new_phrase)


def feature_selection(dataset, dict_to_json, folder, dataset_name, limit):
    dict_to_json = get_extend_tags_tags(dataset, dict_to_json, folder, 'News', limit)

    with open('Feature_Combination.json', 'r') as f:
        feature_combination = json.loads(f.read())
    for feature in feature_combination:
        feature_dataset_dict = dict()
        for key, item in dict_to_json.items():
            feature_dataset_dict[key] = item.copy()
        f = get_bigram_tags if feature['base_tags'] == 'bigram' else get_upos_tags
        f(feature_dataset_dict, dataset_name, feature['filter'], feature['extend'])

        file_name = folder + '/{}_Dataset_{}_{}.json'.format(dataset_name, limit, feature['name'])
        with open(file_name, 'w') as f:
            json.dump(feature_dataset_dict, f)
        