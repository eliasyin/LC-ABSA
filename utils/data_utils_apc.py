# -*- coding: utf-8 -*-
# file: data_utils_apc.py
# author: songyouwei <youwei0314@gmail.com>
# Copyright (C) 2018. All Rights Reserved.

# modified: yangheng<yangheng@m.scnu.edu.cn>

import os
import pickle
import numpy as np
from torch.utils.data import Dataset
import argparse
import json
import torch
import networkx as nx
import spacy
from transformers import BertTokenizer


def parse_experiments(path):
    configs = []

    with open(path, "r", encoding='utf-8') as reader:
        json_config = json.loads(reader.read())
    for id, config in json_config.items():
        # Hyper Parameters
        parser = argparse.ArgumentParser()
        parser.add_argument('--model_name', default=config['model_name'], type=str)
        parser.add_argument('--dataset', default=config['dataset'], type=str, help='twitter, restaurant, laptop')
        parser.add_argument('--optimizer', default=config['optimizer'], type=str)
        parser.add_argument('--initializer', default='xavier_uniform_', type=str)
        parser.add_argument('--learning_rate', default=config['learning_rate'], type=float)
        parser.add_argument('--dropout', default=config['dropout'], type=float)
        parser.add_argument('--l2reg', default=config['l2reg'], type=float)
        parser.add_argument('--num_epoch', default=config['num_epoch'], type=int)
        parser.add_argument('--batch_size', default=config['batch_size'], type=int)
        parser.add_argument('--log_step', default=5, type=int)
        parser.add_argument('--logdir', default=config['logdir'], type=str)
        parser.add_argument('--embed_dim', default=768 if 'bert' in config['model_name'] else 300, type=int)
        parser.add_argument('--hidden_dim', default=768 if 'bert' in config['model_name'] else 300, type=int)
        parser.add_argument('--pretrained_bert_name', default='bert-base-uncased' \
            if 'pretrained_bert_name' not in config else config['pretrained_bert_name'], type=str)
        parser.add_argument('--use_bert_spc', default=True \
            if 'use_bert_spc' not in config else config['use_bert_spc'], type=bool)
        parser.add_argument('--use_dual_bert', default=False \
            if 'use_dual_bert' not in config else config['use_dual_bert'], type=bool)
        parser.add_argument('--max_seq_len', default=config['max_seq_len'], type=int)
        parser.add_argument('--polarities_dim', default=3, type=int)
        parser.add_argument('--hops', default=3, type=int)
        parser.add_argument('--SRD', default=config['SRD'], type=int)
        parser.add_argument('--hlcf', default='parallel' if 'hlcf' not in config else config['hlcf'],
                            choices=['cascade', 'parallel'], type=str)
        parser.add_argument('--lcf', default=config['lcf'], type=str)
        parser.add_argument('--lcfs', default=False if 'lcfs' not in config else config['lcfs'], choices=[True, False],
                            type=bool)
        parser.add_argument('--lca', default=False if 'lca' not in config else config['lca'], choices=[True, False],
                            type=bool)
        parser.add_argument('--lcp', default=False if 'lcp' not in config else config['lcp'], choices=[True, False],
                            type=bool)
        parser.add_argument('--sigma', default=1 if 'sigma' not in config else config['sigma'], type=float)
        parser.add_argument('--repeat', default=config['exp_rounds'], type=bool)
        # index of config
        parser.add_argument('--config_idx', default=id, type=str)
        # The following lines are useless, do not care
        parser.add_argument('--config', default=None, type=str)
        parser.add_argument('--inferring_dataset', default=None, type=str)
        configs.append(parser.parse_args())
    return configs


def build_tokenizer_for_inferring(fnames, max_seq_len, dat_fname=None):
    if dat_fname is not None and os.path.exists(dat_fname):
        print('loading tokenizer:', dat_fname)
        tokenizer = pickle.load(open(dat_fname, 'rb'))
    else:
        text = ''
        for fname in fnames:
            fin = open(fname, 'r', encoding='utf-8', newline='\n', errors='ignore')
            lines = fin.readlines()
            fin.close()
            for i in range(len(lines)):
                text_left, aspect, text_right = lines[i].split('$')
                text = ' '.join([text_left, aspect, text_right.replace('\r\n','')]),
        tokenizer = Tokenizer(max_seq_len)
        tokenizer.fit_on_text(text[0])
        pickle.dump(tokenizer, open(dat_fname, 'wb'))
    return tokenizer


def build_tokenizer(fnames, max_seq_len, dat_fname=None):
    text = ''
    for fname in fnames:
        fin = open(fname, 'r', encoding='utf-8', newline='\n', errors='ignore')
        lines = fin.readlines()
        fin.close()
        for i in range(0, len(lines), 3):
                text_left, _, text_right = [s.lower().strip() for s in lines[i].partition("$T$")]
                aspect = lines[i + 1].lower().strip()
                text_raw = text_left + " " + aspect + " " + text_right
                text += text_raw + " "

    tokenizer = Tokenizer(max_seq_len)
    tokenizer.fit_on_text(text)
    return tokenizer


def _load_word_vec(path, word2idx=None, embed_dim=300):
    fin = open(path, 'r', encoding='utf-8', newline='\n', errors='ignore')
    word_vec = {}
    for line in fin:
        tokens = line.rstrip().split()
        if word2idx is None or tokens[0] in word2idx.keys():
            word_vec[tokens[0]] = np.asarray(tokens[len(tokens) - embed_dim:len(tokens)], dtype='float32')
    return word_vec


def build_embedding_matrix(word2idx, embed_dim, dat_fname):
    if os.path.exists(dat_fname):
        print('loading embedding:', dat_fname)
        embedding_matrix = pickle.load(open(dat_fname, 'rb'))
    else:
        print('loading word vectors...')
        embedding_matrix = np.zeros((len(word2idx) + 2, embed_dim))  # idx 0 and len(word2idx)+1 are all-zeros
        fname = './glove.twitter.27B/glove.twitter.27B.' + str(embed_dim) + 'd.txt' \
            if embed_dim != 300 else './glove.840B.300d.txt'
        path = '/home/ycf19/tools/features/glove'
        fname = os.path.join(path, fname)
        word_vec = _load_word_vec(fname, word2idx=word2idx)
        print('building embedding:', dat_fname)
        for word, i in word2idx.items():
            vec = word_vec.get(word)
            if vec is not None:
                embedding_matrix[i] = vec
        pickle.dump(embedding_matrix, open(dat_fname, 'wb'))
    return embedding_matrix


def pad_and_truncate(sequence, maxlen, dtype='int64', padding='post', truncating='post', value=0):
    x = (np.ones(maxlen) * value).astype(dtype)
    if truncating == 'pre':
        trunc = sequence[-maxlen:]
    else:
        trunc = sequence[:maxlen]
    trunc = np.asarray(trunc, dtype=dtype)
    if padding == 'post':
        x[:len(trunc)] = trunc
    else:
        x[-len(trunc):] = trunc
    return x


class Tokenizer(object):
    def __init__(self, max_seq_len, lower=True):
        self.lower = lower
        self.max_seq_len = max_seq_len
        self.word2idx = {}
        self.idx2word = {}
        self.idx = 1
        self.cls_token = "[CLS]"
        self.sep_token = "[SEP]"
        self.tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

    def fit_on_text(self, text):
        if self.lower:
            text = text.lower()
        words = text.split()
        for word in words:
            if word not in self.word2idx:
                self.word2idx[word] = self.idx
                self.idx2word[self.idx] = word
                self.idx += 1

    def text_to_sequence(self, text, reverse=False, padding='post', truncating='post'):
        if self.lower:
            text = text.lower()
        words = text.split()
        unknownidx = len(self.word2idx) + 1
        sequence = [self.word2idx[w] if w in self.word2idx else unknownidx for w in words]
        if len(sequence) == 0:
            sequence = [0]
        if reverse:
            sequence = sequence[::-1]
        return pad_and_truncate(sequence, self.max_seq_len, padding=padding, truncating=truncating)

    def tokenize(self, text, dep_dist, reverse=False, padding='post', truncating='post'):
        r'''
        input:
        --------------
        text : 一个句子tokenize之后的列表，包含[CLS] [SEP]

        dep_dist : 句子中每个token到aspect的距离，包含[CLS] [SEP]

        output:
        ------------------
        sequence : BertTokenizer.encode的结果，并补齐到指定长度，包含[CLS] [SEP]

        dep_dist : 将dep_dist补齐到指定长度
        '''
        sequence, distances = [], []
        for word, dist in zip(text, dep_dist):
            tokens = self.tokenizer.tokenize(word)
            for jx, token in enumerate(tokens):
                sequence.append(token)
                distances.append(dist)
        sequence = self.tokenizer.convert_tokens_to_ids(sequence)

        if len(sequence) == 0:
            sequence = [0]
            dep_dist = [0]
        if reverse:
            sequence = sequence[::-1]
            dep_dist = dep_dist[::-1]
        sequence = pad_and_truncate(
            sequence, self.max_seq_len, padding=padding, truncating=truncating)
        dep_dist = pad_and_truncate(
            dep_dist, self.max_seq_len, padding=padding, truncating=truncating, value=self.max_seq_len)

        return sequence, dep_dist
# class Tokenizer4Bert:
#     def __init__(self, bert_tokenizer, max_seq_len):
#         self.tokenizer = bert_tokenizer
#         self.max_seq_len = max_seq_len
#
#     def text_to_sequence(self, text, reverse=False, padding='post', truncating='post'):
#         sequence = self.tokenizer.convert_tokens_to_ids(self.tokenizer.tokenize(text))
#         if len(sequence) == 0:
#             sequence = [0]
#         if reverse:
#             sequence = sequence[::-1]
#         return pad_and_truncate(sequence, self.max_seq_len, padding=padding, truncating=truncating)
#
# class Tokenizer(object):
#     def __init__(self, max_seq_len, lower=True):
#         self.lower = lower
#         self.max_seq_len = max_seq_len
#         self.word2idx = {}
#         self.idx2word = {}
#         self.idx = 1
#
#     def fit_on_text(self, text):
#         if self.lower:
#             text = text.lower()
#         words = text.split()
#         for word in words:
#             if word not in self.word2idx:
#                 self.word2idx[word] = self.idx
#                 self.idx2word[self.idx] = word
#                 self.idx += 1
#
#     def text_to_sequence(self, text, reverse=False, padding='post', truncating='post'):
#         if self.lower:
#             text = text.lower()
#         words = text.split()
#         unknownidx = len(self.word2idx)+1
#         sequence = [self.word2idx[w] if w in self.word2idx else unknownidx for w in words]
#         if len(sequence) == 0:
#             sequence = [0]
#         if reverse:
#             sequence = sequence[::-1]
#         return pad_and_truncate(sequence, self.max_seq_len, padding=padding, truncating=truncating)

class Tokenizer4Bert:
    def __init__(self, tokenizer, max_seq_len):
        self.tokenizer = tokenizer
        self.cls_token = tokenizer.cls_token
        self.sep_token = tokenizer.sep_token
        self.max_seq_len = max_seq_len

    def text_to_sequence(self, text, reverse=False, padding='post', truncating='post'):
        r'''
        接收一个字符串输入，输出是不包含[CLS] [SEP]的向量

        input :
        ----------
        text : 文本

        reverse : 

        padding : 'post' 表示在embedding后边补加数据

        truncating : 'post' 表示保留前边的数据

        '''
        sequence = self.tokenizer.convert_tokens_to_ids(self.tokenizer.tokenize(text))
        if len(sequence) == 0:
            sequence = [0]
        if reverse:
            sequence = sequence[::-1]
        return pad_and_truncate(sequence, self.max_seq_len, padding=padding, truncating=truncating)

    # Group distance to aspect of an original word to its corresponding subword token
    def tokenize(self, text, dep_dist, reverse=False, padding='post', truncating='post'):
        r'''
        input:
        --------------
        text : 一个句子tokenize之后的列表，包含[CLS] [SEP]

        dep_dist : 根据spacy依存分析计算出句子中每个token到aspect的距离，包含[CLS] [SEP]

        output:
        ------------------
        sequence : BertTokenizer.encode的结果，并补齐到指定长度，包含[CLS] [SEP]

        dep_dist : 将dep_dist补齐到指定长度
        '''
        sequence, distances = [],[]
        for word,dist in zip(text,dep_dist):
            tokens = self.tokenizer.tokenize(word)
            for jx,token in enumerate(tokens):
                sequence.append(token)
                distances.append(dist)
        sequence = self.tokenizer.convert_tokens_to_ids(sequence)

        if len(sequence) == 0:
            sequence = [0]
            dep_dist = [0]
        if reverse:
            sequence = sequence[::-1]
            dep_dist = dep_dist[::-1]
        sequence = pad_and_truncate(sequence, self.max_seq_len, padding=padding, truncating=truncating)
        dep_dist = pad_and_truncate(dep_dist, self.max_seq_len, padding=padding, truncating=truncating,value=self.max_seq_len)

        return sequence, dep_dist



class ABSADataset(Dataset):
    input_colses = {
        'bert_base': ['text_raw_bert_indices'],
        'bert_spc': ['text_raw_bert_indices', 'bert_segments_ids'],
        'lca_lstm': ['text_bert_indices', 'text_raw_bert_indices', 'lca_ids', 'lcf_vec'],
        'lca_glove': ['text_bert_indices', 'text_raw_bert_indices', 'lca_ids', 'lcf_vec'],
        'lca_bert': ['text_bert_indices', 'text_raw_bert_indices', 'bert_segments_ids', 'lca_ids', 'lcf_vec'],
        'lcf_glove': ['text_bert_indices', 'text_raw_bert_indices', 'lcf_vec', ],
        'lcf_bert': ['text_bert_indices', 'text_raw_bert_indices', 'bert_segments_ids', 'lcf_vec'],
        'hlcf_glove': ['text_bert_indices', 'text_raw_bert_indices', 'lcf_vec'],
        'hlcf_bert': ['text_bert_indices', 'text_raw_bert_indices', 'bert_segments_ids', 'lcf_vec'],
        'lstm': ['text_raw_indices'],
        'td_lstm': ['text_left_with_aspect_indices', 'text_right_with_aspect_indices'],
        'tc_lstm': ['text_left_with_aspect_indices', 'text_right_with_aspect_indices', 'aspect_indices'],
        'atae_lstm': ['text_raw_indices', 'aspect_indices'],
        'ian': ['text_raw_indices', 'aspect_indices'],
        'memnet': ['text_raw_without_aspect_indices', 'aspect_indices'],
        'ram': ['text_raw_indices', 'aspect_indices', 'text_left_indices'],
        'cabasc': ['text_raw_indices', 'aspect_indices', 'text_left_with_aspect_indices',
                   'text_right_with_aspect_indices'],
        'tnet_lf': ['text_raw_indices', 'aspect_indices', 'aspect_in_text'],
        'aoa': ['text_raw_indices', 'aspect_indices'],
        'mgan': ['text_raw_indices', 'aspect_indices', 'text_left_indices'],
        'aen_bert': ['text_raw_bert_indices', 'aspect_bert_indices'],
    }

    def __init__(self, fname, tokenizer, opt):

        fin = open(fname, 'r', encoding='utf-8', newline='\n', errors='ignore')
        lines = fin.readlines()
        fin.close()
        print('buliding word indices...')
        all_data = []

        def get_lca_ids_and_cdm_vec(text_ids, aspect_indices, syntactical_dist=None):
            r'''
            目前每次只处理一句话中的一个aspect

            output : 
            -------
            lca_ids : 范围在 max(aspect_begin - SRD, 0) ~ aspect_begin + SRD + aspect_len -1 范围内toekn对应的id为1，其余为0

            cdm_vec : 范围在 max(aspect_begin - SRD, 0) ~ aspect_begin + SRD + aspect_len -1 范围内toekn对应的mask为1，其余为0
            '''
            lca_ids = np.ones((opt.max_seq_len), dtype=np.float32)
            cdm_vec = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
            aspect_len = np.count_nonzero(aspect_indices) - 2
            aspect_begin = np.argwhere(text_ids == aspect_indices[1])[0]
            mask_begin = aspect_begin - opt.SRD if aspect_begin >= opt.SRD else 0
            # mask_begin = aspect_begin
            for i in range(opt.max_seq_len):
                # if i < mask_begin or i > aspect_begin + aspect_len - 1:
                if i < mask_begin or i > aspect_begin + aspect_len + opt.SRD - 1:
                    lca_ids[i] = 0
                    cdm_vec[i] = np.zeros((opt.embed_dim), dtype=np.float32)
            if opt.lcfs and syntactical_dist.all():
                for i in range(opt.max_seq_len):
                    if syntactical_dist[i] < opt.SRD:
                        lca_ids[i] = 1
                        cdm_vec[i] = np.ones((opt.embed_dim), dtype=np.float32)
            return lca_ids, cdm_vec

        def get_hierarchical_cdm_vec(text_ids, aspect_indices):
            cdm_vec3 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
            cdm_vec5 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
            cdm_vec10 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
            aspect_len = np.count_nonzero(aspect_indices) - 2
            aspect_begin = np.argwhere(text_ids == aspect_indices[1])[0]
            mask_begin = aspect_begin - opt.SRD if aspect_begin >= opt.SRD else 0
            for i in range(opt.max_seq_len):
                if i < mask_begin or i > aspect_begin + aspect_len + 3 - 1:
                    cdm_vec3[i] = np.zeros((opt.embed_dim), dtype=np.float32)
            mask_begin = aspect_begin - 5 if aspect_begin >= 5 else 0
            for i in range(opt.max_seq_len):
                if i < mask_begin or i > aspect_begin + aspect_len + 5 - 1:
                    cdm_vec5[i] = np.zeros((opt.embed_dim), dtype=np.float32)
            mask_begin = aspect_begin - 10 if aspect_begin >= 10 else 0
            for i in range(opt.max_seq_len):
                if i < mask_begin or i > aspect_begin + aspect_len + 10 - 1:
                    cdm_vec10[i] = np.zeros((opt.embed_dim), dtype=np.float32)
            return cdm_vec3, cdm_vec5, cdm_vec10,

        def get_cdw_vec(text_ids, aspect_indices, syntactical_dist=None):
            cdw_vec = np.zeros((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
            aspect_len = np.count_nonzero(aspect_indices) - 2
            aspect_begin = np.argwhere(text_ids == aspect_indices[1])[0]
            asp_avg_index = (aspect_begin * 2 + aspect_len) / 2
            text_len = np.flatnonzero(text_ids)[-1] + 1
            if opt.lcfs and syntactical_dist.all():
                for i in range(text_len):
                    if syntactical_dist[i] > opt.SRD:
                        w = 1 - syntactical_dist[i] / text_len
                        cdw_vec[i] = w * np.ones((opt.embed_dim), dtype=np.float32)
                    else:
                        cdw_vec[i] = np.ones((opt.embed_dim), dtype=np.float32)
            else:
                for i in range(text_len):
                    if abs(i - asp_avg_index) + aspect_len / 2 > opt.SRD:
                        w = 1 - (abs(i - asp_avg_index) + aspect_len / 2 - opt.SRD) / text_len
                        cdw_vec[i] = w * np.ones((opt.embed_dim), dtype=np.float32)
                    else:
                        cdw_vec[i] = np.ones((opt.embed_dim), dtype=np.float32)
            return cdw_vec

        def get_hierarchical_cdw_vec(text_ids, aspect_indices):
            cdw_vec3 = np.zeros((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
            cdw_vec5 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
            cdw_vec10 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
            aspect_len = np.count_nonzero(aspect_indices) - 2
            aspect_begin = np.argwhere(text_ids == aspect_indices[1])[0]
            asp_avg_index = (aspect_begin * 2 + aspect_len) / 2
            text_len = np.flatnonzero(text_ids)[-1] + 1
            for i in range(text_len):
                if abs(i - asp_avg_index) + aspect_len / 2 > 3:
                    w = 1 - (abs(i - asp_avg_index) + aspect_len / 2 - 3) / text_len
                    cdw_vec3[i] = w * np.ones((opt.embed_dim), dtype=np.float32)
                else:
                    cdw_vec3[i] = np.ones((opt.embed_dim), dtype=np.float32)
            for i in range(text_len):
                if abs(i - asp_avg_index) + aspect_len / 2 > 5:
                    w = 1 - (abs(i - asp_avg_index) + aspect_len / 2 - 5) / text_len
                    cdw_vec5[i] = w * np.ones((opt.embed_dim), dtype=np.float32)
                else:
                    cdw_vec5[i] = np.ones((opt.embed_dim), dtype=np.float32)
            for i in range(text_len):
                if abs(i - asp_avg_index) + aspect_len / 2 > 10:
                    w = 1 - (abs(i - asp_avg_index) + aspect_len / 2 - 10) / text_len
                    cdw_vec10[i] = w * np.ones((opt.embed_dim), dtype=np.float32)
                else:
                    cdw_vec10[i] = np.ones((opt.embed_dim), dtype=np.float32)

            return cdw_vec3, cdw_vec5, cdw_vec10
        # 初始化上边的函数之后构建数据
        for i in range(0, len(lines), 3):
            if lines[i].count('$T$') == 1:
                text_left, _, text_right = [s.lower().strip() for s in lines[i].partition("$T$")]
                polarity = lines[i + 2].strip()
                polarity = int(polarity) if opt.dataset in {'camera', 'notebook', 'car', 'phone'} else int(polarity) + 1
                aspect = lines[i + 1].lower().strip()
            else:
                text_left = lines[i].replace('$', '').strip()
                text_right = ''
                polarity = 0
                aspect = lines[i][lines[i].find('$')+1:]
                aspect = aspect[:aspect.find('$')].strip()

            aspect_indices = tokenizer.text_to_sequence(aspect)
            aspect_len = np.sum(aspect_indices != 0)

            # Trick: dynamic truncation on input text
            text_left = ' '.join(text_left.split(' ')[int(-(tokenizer.max_seq_len - aspect_len) / 2) - 1:])
            text_right = ' '.join(text_right.split(' ')[:int((tokenizer.max_seq_len - aspect_len) / 2) + 1])
            text_left = ' '.join(text_left.split(' '))
            text_right = ' '.join(text_right.split(' '))
            text_raw = text_left + ' ' + aspect + ' ' + text_right

            text_raw_without_aspect_indices = tokenizer.text_to_sequence(text_left + " " + text_right)
            text_left_indices = tokenizer.text_to_sequence(text_left)
            text_left_with_aspect_indices = tokenizer.text_to_sequence(text_left + " " + aspect)
            text_right_indices = tokenizer.text_to_sequence(text_right, reverse=True)
            text_right_with_aspect_indices = tokenizer.text_to_sequence(" " + aspect + " " + text_right, reverse=True)
            aspect_indices = tokenizer.text_to_sequence(aspect)
            left_context_len = np.sum(text_left_indices != 0)
            aspect_len = np.sum(aspect_indices != 0)
            aspect_in_text = torch.tensor([left_context_len.item(), (left_context_len + aspect_len - 1).item()])

            text_raw_indices = tokenizer.text_to_sequence(text_raw)
            text_bert_indices = tokenizer.text_to_sequence(
                '[CLS] ' + text_left + " " + aspect + " " + text_right + ' [SEP] ' + aspect + " [SEP]")
            # np.sum(text_raw_indices != 0) + 2 : text中token的个数 +[CLS] [SEP];  aspect_len + 1 : aspect的token个数 + [SEP]
            bert_segments_ids = np.asarray([0] * (np.sum(text_raw_indices != 0) + 2) + [1] * (aspect_len + 1))
            bert_segments_ids = pad_and_truncate(bert_segments_ids, tokenizer.max_seq_len)

            text_raw_bert_indices = tokenizer.text_to_sequence(
                "[CLS] " + text_left + " " + aspect + " " + text_right + " [SEP]")
            aspect_bert_indices = tokenizer.text_to_sequence("[CLS] " + aspect + " [SEP]")

            # Find distance in dependency parsing tree
            # 这里分词用的预训练模型来自spacy而不是bert
            raw_tokens, dist = calculate_dep_dist(text_raw, aspect)
            # 这里的raw_tokens仅仅是分隔后的单个单词列表，所以还需要添加[CLS][SEP]
            raw_tokens.insert(0, tokenizer.cls_token)
            dist.insert(0, 0)  # 这里添加0表明[SEP]  [CLS]和aspect的没有依存关系
            raw_tokens.append(tokenizer.sep_token)
            dist.append(0)
            #  distance_to_aspect : pad之后的依存树距离
            _, distance_to_aspect = tokenizer.tokenize(raw_tokens, dist)

            if 'lca' in opt.model_name:
                lca_ids, lcf_vec = get_lca_ids_and_cdm_vec(text_bert_indices, aspect_bert_indices, distance_to_aspect)
                lcf_vec = torch.from_numpy(lcf_vec)
                lca_ids = torch.from_numpy(lca_ids).long()
            elif 'lcf' in opt.model_name:
                if 'cdm' in opt.lcf:
                    if 'hlcf' in opt.model_name:
                        lcf_vec3, lcf_vec5, lcf_vec10, = get_hierarchical_cdm_vec(text_bert_indices,aspect_bert_indices)
                        lcf_vec = (torch.from_numpy(lcf_vec3), torch.from_numpy(lcf_vec5), torch.from_numpy(lcf_vec10))
                    else:
                        _, lcf_vec = get_lca_ids_and_cdm_vec(text_bert_indices, aspect_bert_indices, distance_to_aspect)
                        lcf_vec = torch.from_numpy(lcf_vec)
                elif 'cdw' in opt.lcf:
                    if 'hlcf' in opt.model_name:
                        lcf_vec3, lcf_vec5, lcf_vec10, = get_hierarchical_cdw_vec(text_bert_indices,aspect_bert_indices)
                        lcf_vec = (torch.from_numpy(lcf_vec3), torch.from_numpy(lcf_vec5), torch.from_numpy(lcf_vec10))
                    else:
                        lcf_vec = get_cdw_vec(text_bert_indices, aspect_bert_indices, distance_to_aspect)
                        lcf_vec = torch.from_numpy(lcf_vec)
                elif 'fusion' in opt.lcf:
                    raise NotImplementedError('LCF-Fusion is not recommended due to its low efficiency!')
                else:
                    raise KeyError('Invalid LCF Mode!')

            data = {
                'text_raw': text_raw,
                'aspect': aspect,
                'lca_ids': lca_ids if 'lca_ids' in ABSADataset.input_colses[opt.model_name] else 0,
                'lcf_vec': lcf_vec if 'lcf_vec' in ABSADataset.input_colses[opt.model_name] else 0,
                'text_bert_indices': text_bert_indices if 'text_bert_indices' in ABSADataset.input_colses[opt.model_name] else 0,
                'bert_segments_ids': bert_segments_ids if 'bert_segments_ids' in ABSADataset.input_colses[opt.model_name] else 0,

                'aspect_bert_indices': aspect_bert_indices if 'aspect_bert_indices' in ABSADataset.input_colses[opt.model_name] else 0,
                'text_raw_indices': text_raw_indices if 'text_raw_indices' in ABSADataset.input_colses[opt.model_name] else 0,
                'aspect_indices': aspect_indices if 'aspect_indices' in ABSADataset.input_colses[opt.model_name] else 0,
                'text_left_indices': text_left_indices if 'text_left_indices' in ABSADataset.input_colses[opt.model_name] else 0,
                'aspect_in_text': aspect_in_text if 'aspect_in_text' in ABSADataset.input_colses[opt.model_name] else 0,

                'text_raw_without_aspect_indices': text_raw_without_aspect_indices
                if 'text_raw_without_aspect_indices' in ABSADataset.input_colses[opt.model_name] else 0,

                'text_left_with_aspect_indices': text_left_with_aspect_indices
                if 'text_left_with_aspect_indices' in ABSADataset.input_colses[opt.model_name] else 0,

                'text_right_indices': text_right_indices
                if 'text_right_indices' in ABSADataset.input_colses[opt.model_name] else 0,

                'text_right_with_aspect_indices': text_right_with_aspect_indices
                if 'text_right_with_aspect_indices' in ABSADataset.input_colses[opt.model_name] else 0,

                'text_raw_bert_indices': text_raw_bert_indices
                if 'text_raw_bert_indices' in ABSADataset.input_colses[opt.model_name] else 0,

                'polarity': polarity,
            }
            for _, item in enumerate(data):
                data[item] = torch.tensor(data[item]) if type(item) is not str else data[item]
            all_data.append(data)
        self.data = all_data

    def __getitem__(self, index):
        return self.data[index]

    def __len__(self):
        return len(self.data)

# class ABSAInferDataset(Dataset):
#
#     def __init__(self, fname, tokenizer, opt):
#
#         fin = open(fname, 'r', encoding='utf-8', newline='\n', errors='ignore')
#         lines = fin.readlines()
#         fin.close()
#         print('buliding word indices...')
#         all_data = []
#
#         def get_lca_ids_and_cdm_vec(text_ids, aspect_indices):
#             lca_ids = np.ones((opt.max_seq_len), dtype=np.float32)
#             cdm_vec = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
#             aspect_len = np.count_nonzero(aspect_indices) - 2
#             aspect_begin = np.argwhere(text_ids == aspect_indices[1])[0]
#             mask_begin = aspect_begin - opt.SRD if aspect_begin >= opt.SRD else 0
#             for i in range(opt.max_seq_len):
#                 if i < mask_begin or i > aspect_begin + aspect_len + opt.SRD - 1:
#                     lca_ids[i] = 0
#                     cdm_vec[i] = np.zeros((opt.embed_dim), dtype=np.float32)
#             return lca_ids, cdm_vec
#
#         def get_hierarchical_cdm_vec(text_ids, aspect_indices):
#             cdm_vec3 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
#             cdm_vec5 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
#             cdm_vec10 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
#             aspect_len = np.count_nonzero(aspect_indices) - 2
#             aspect_begin = np.argwhere(text_ids == aspect_indices[1])[0]
#             mask_begin = aspect_begin - opt.SRD if aspect_begin >= opt.SRD else 0
#             for i in range(opt.max_seq_len):
#                 if i < mask_begin or i > aspect_begin + aspect_len + 3 - 1:
#                     cdm_vec3[i] = np.zeros((opt.embed_dim), dtype=np.float32)
#             mask_begin = aspect_begin - 5 if aspect_begin >= 5 else 0
#             for i in range(opt.max_seq_len):
#                 if i < mask_begin or i > aspect_begin + aspect_len + 5 - 1:
#                     cdm_vec5[i] = np.zeros((opt.embed_dim), dtype=np.float32)
#             mask_begin = aspect_begin - 10 if aspect_begin >= 10 else 0
#             for i in range(opt.max_seq_len):
#                 if i < mask_begin or i > aspect_begin + aspect_len + 10 - 1:
#                     cdm_vec10[i] = np.zeros((opt.embed_dim), dtype=np.float32)
#             return cdm_vec3, cdm_vec5, cdm_vec10,
#
#         def get_cdw_vec(text_ids, aspect_indices):
#             cdw_vec = np.zeros((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
#             aspect_len = np.count_nonzero(aspect_indices) - 2
#             aspect_begin = np.argwhere(text_ids == aspect_indices[1])[0]
#             asp_avg_index = (aspect_begin * 2 + aspect_len) / 2
#             text_len = np.flatnonzero(text_ids)[-1] + 1
#             for i in range(text_len):
#                 if abs(i - asp_avg_index) + aspect_len / 2 > opt.SRD:
#                     w = 1 - (abs(i - asp_avg_index) + aspect_len / 2 - opt.SRD) / text_len
#                     cdw_vec[i] = w * np.ones((opt.embed_dim), dtype=np.float32)
#                 else:
#                     cdw_vec[i] = np.ones((opt.embed_dim), dtype=np.float32)
#             return cdw_vec
#
#         def get_hierarchical_cdw_vec(text_ids, aspect_indices):
#             cdw_vec3 = np.zeros((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
#             cdw_vec5 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
#             cdw_vec10 = np.ones((opt.max_seq_len, opt.embed_dim), dtype=np.float32)
#             aspect_len = np.count_nonzero(aspect_indices) - 2
#             aspect_begin = np.argwhere(text_ids == aspect_indices[1])[0]
#             asp_avg_index = (aspect_begin * 2 + aspect_len) / 2
#             text_len = np.flatnonzero(text_ids)[-1] + 1
#             for i in range(text_len):
#                 if abs(i - asp_avg_index) + aspect_len / 2 > 3:
#                     w = 1 - (abs(i - asp_avg_index) + aspect_len / 2 - 3) / text_len
#                     cdw_vec3[i] = w * np.ones((opt.embed_dim), dtype=np.float32)
#                 else:
#                     cdw_vec3[i] = np.ones((opt.embed_dim), dtype=np.float32)
#             for i in range(text_len):
#                 if abs(i - asp_avg_index) + aspect_len / 2 > 5:
#                     w = 1 - (abs(i - asp_avg_index) + aspect_len / 2 - 5) / text_len
#                     cdw_vec5[i] = w * np.ones((opt.embed_dim), dtype=np.float32)
#                 else:
#                     cdw_vec5[i] = np.ones((opt.embed_dim), dtype=np.float32)
#             for i in range(text_len):
#                 if abs(i - asp_avg_index) + aspect_len / 2 > 10:
#                     w = 1 - (abs(i - asp_avg_index) + aspect_len / 2 - 10) / text_len
#                     cdw_vec10[i] = w * np.ones((opt.embed_dim), dtype=np.float32)
#                 else:
#                     cdw_vec10[i] = np.ones((opt.embed_dim), dtype=np.float32)
#
#             return cdw_vec3, cdw_vec5, cdw_vec10
#
#         for i in range(len(lines)):
#             try:
#                 text_left, aspect, text_right = lines[i].split('$')
#             except:
#                 continue
#             aspect_indices = tokenizer.text_to_sequence(aspect)
#             aspect_len = np.sum(aspect_indices != 0)
#
#             # Trick: dynamic truncation on input text
#             text_left = ' '.join(text_left.split(' ')[int(-(tokenizer.max_seq_len - aspect_len) / 2) - 1:])
#             text_right = ' '.join(text_right.split(' ')[:int((tokenizer.max_seq_len - aspect_len) / 2) + 1])
#             text_left = ' '.join(text_left.split(' '))
#             text_right = ' '.join(text_right.split(' '))
#             text_raw = text_left + ' ' + aspect + ' ' + text_right
#
#             # text_raw_indices = tokenizer.text_to_sequence(text_left + " " + aspect + " " + text_right)
#             text_raw_without_aspect_indices = tokenizer.text_to_sequence(text_left + " " + text_right)
#             text_left_indices = tokenizer.text_to_sequence(text_left)
#             text_left_with_aspect_indices = tokenizer.text_to_sequence(text_left + " " + aspect)
#             text_right_indices = tokenizer.text_to_sequence(text_right, reverse=True)
#             text_right_with_aspect_indices = tokenizer.text_to_sequence(" " + aspect + " " + text_right, reverse=True)
#             aspect_indices = tokenizer.text_to_sequence(aspect)
#             left_context_len = np.sum(text_left_indices != 0)
#             aspect_len = np.sum(aspect_indices != 0)
#             aspect_in_text = torch.tensor([left_context_len.item(), (left_context_len + aspect_len - 1).item()])
#
#             # Find distance in dependency parsing tree
#             raw_tokens, dist = calculate_dep_dist(text_raw, aspect)
#             raw_tokens.insert(0,tokenizer.cls_token)
#             dist.insert(0,0)
#             raw_tokens.append(tokenizer.sep_token)
#             dist.append(0)
#
#             _, distance_to_aspect = tokenizer.tokenize(raw_tokens, dist)
#
#             text_raw_indices = tokenizer.text_to_sequence(text_raw)
#             text_bert_indices = tokenizer.text_to_sequence(
#                 '[CLS] ' + text_left + " " + aspect + " " + text_right + ' [SEP] ' + aspect + " [SEP]")
#             bert_segments_ids = np.asarray([0] * (np.sum(text_raw_indices != 0) + 2) + [1] * (aspect_len + 1))
#             bert_segments_ids = pad_and_truncate(bert_segments_ids, tokenizer.max_seq_len)
#
#             text_raw_bert_indices = tokenizer.text_to_sequence(
#                 "[CLS] " + text_left + " " + aspect + " " + text_right + " [SEP]")
#             aspect_bert_indices = tokenizer.text_to_sequence("[CLS] " + aspect + " [SEP]")
#             if 'lca' in opt.model_name:
#                 lca_ids, lcf_vec = get_lca_ids_and_cdm_vec(text_bert_indices, aspect_bert_indices)
#                 lcf_vec = torch.from_numpy(lcf_vec)
#                 lca_ids = torch.from_numpy(lca_ids).long()
#             elif 'lcf' in opt.model_name:
#                 if 'cdm' in opt.lcf:
#                     if 'hlcf' in opt.model_name:
#                         lcf_vec3, lcf_vec5, lcf_vec10, = get_hierarchical_cdm_vec(text_bert_indices,aspect_bert_indices)
#                         lcf_vec = (torch.from_numpy(lcf_vec3), torch.from_numpy(lcf_vec5), torch.from_numpy(lcf_vec10))
#                     else:
#                         _, lcf_vec = get_lca_ids_and_cdm_vec(text_bert_indices, aspect_bert_indices)
#                         lcf_vec = torch.from_numpy(lcf_vec)
#                 elif 'cdw' in opt.lcf:
#                     if 'hlcf' in opt.model_name:
#                         lcf_vec3, lcf_vec5, lcf_vec10, = get_hierarchical_cdw_vec(text_bert_indices,aspect_bert_indices)
#                         lcf_vec = (torch.from_numpy(lcf_vec3), torch.from_numpy(lcf_vec5), torch.from_numpy(lcf_vec10))
#                     else:
#                         lcf_vec = get_cdw_vec(text_bert_indices, aspect_bert_indices)
#                         lcf_vec = torch.from_numpy(lcf_vec)
#                 elif 'fusion' in opt.lcf:
#                     raise NotImplementedError('LCF-Fusion is not recommended due to its low efficiency!')
#                 else:
#                     raise KeyError('Invalid LCF Mode!')
#
#             data = {
#                 'sentence': ' '.join([text_left, aspect, text_right.replace('\r\n','')]),
#                 'aspect': aspect,
#                 'lca_ids': lca_ids if 'lca_ids' in ABSADataset.input_colses[opt.model_name] else 0,
#                 'lcf_vec': lcf_vec if 'lcf_vec' in ABSADataset.input_colses[opt.model_name] else 0,
#                 'text_bert_indices': text_bert_indices if 'text_bert_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#                 'bert_segments_ids': bert_segments_ids if 'bert_segments_ids' in ABSADataset.input_colses[opt.model_name] else 0,
#
#                 'aspect_bert_indices': aspect_bert_indices if 'aspect_bert_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#                 'text_raw_indices': text_raw_indices if 'text_raw_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#                 'aspect_indices': aspect_indices if 'aspect_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#                 'text_left_indices': text_left_indices if 'text_left_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#                 'aspect_in_text': aspect_in_text if 'aspect_in_text' in ABSADataset.input_colses[opt.model_name] else 0,
#
#                 'text_raw_without_aspect_indices': text_raw_without_aspect_indices
#                 if 'text_raw_without_aspect_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#
#                 'text_left_with_aspect_indices': text_left_with_aspect_indices
#                 if 'text_left_with_aspect_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#
#                 'text_right_indices': text_right_indices
#                 if 'text_right_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#
#                 'text_right_with_aspect_indices': text_right_with_aspect_indices
#                 if 'text_right_with_aspect_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#
#                 'text_raw_bert_indices': text_raw_bert_indices
#                 if 'text_raw_bert_indices' in ABSADataset.input_colses[opt.model_name] else 0,
#             }
#             all_data.append(data)
#         self.data = all_data
#
#     def __getitem__(self, index):
#         return self.data[index]
#
#     def __len__(self):
#         return len(self.data)

nlp = spacy.load("en_core_web_sm")
def calculate_dep_dist(sentence,aspect):
    r'''
    根据句法解析树计算各个token到aspect的最短距离
    input : 
    -----------
    sentence : 完整句子
    aspect : aspect
    '''
    terms = [a.lower() for a in aspect.split()]
    doc = nlp(sentence)
    # Load spacy's dependency tree into a networkx graph
    edges = []
    cnt = 0
    term_ids = [0] * len(terms) # aspect
    for token in doc:
        # Record the position of aspect terms
        if cnt < len(terms) and token.lower_ == terms[cnt]:
            term_ids[cnt] = token.i
            cnt += 1

        for child in token.children:
            # edges 添加的是句法依存解析树中的起点和终点
            edges.append(('{}_{}'.format(token.lower_,token.i),
                          '{}_{}'.format(child.lower_,child.i)))

    graph = nx.Graph(edges)

    dist = [0.0]*len(doc)
    text = [0]*len(doc)
    for i,word in enumerate(doc):
        source = '{}_{}'.format(word.lower_,word.i)
        sum = 0
        for term_id,term in zip(term_ids,terms):
            target = '{}_{}'.format(term, term_id)
            try:
                sum += nx.shortest_path_length(graph,source=source,target=target)
            except:
                sum += len(doc) # No connection between source and target
        dist[i] = sum/len(terms)
        text[i] = word.text
    return text,dist
