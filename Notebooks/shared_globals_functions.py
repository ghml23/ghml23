grtr_rt = 2
td_version = 1 # testdata version
grtr_fn = "/home/manuel/d3tect-tools/jupyter/github-threat-detection-repos-f.csv"

grtr_version = 1
grtr = f'identified_repos_v{grtr_version}'

github_data_folder = '/home/manuel/d3tect-gh'

import pandas as pd
import os

def get_identified_repos(grtr_fn, grtr_rt):
    print(f"reading from disk {grtr_fn}")
    identified_repos = pd.read_csv(grtr_fn)
    
    return identified_repos


def to_disk(obj, name):
    directory = f'{os.getcwd()}/raw_testdata_v{td_version}'
    if not os.path.exists(directory):
        # If it doesn't exist, create it
        os.makedirs(directory)
    file=f'{directory}/{name}.pkl'
    print(file)
    obj.to_pickle(file)

def to_disk_results(obj, name, subdir=''):
    directory = f'{os.getcwd()}/raw_testdata_v{td_version}/results/{subdir}'
    if not os.path.exists(directory):
        # If it doesn't exist, create it
        os.makedirs(directory)
    file = f'{directory}/{name}.pkl'
    print(f'writing {file}')
    obj.to_pickle(f'{file}')

def from_disk(name):
    directory = f'{os.getcwd()}/raw_testdata_v{td_version}'
    file=f'{directory}/{name}.pkl'
    print(f'reading {file}')
    return pd.read_pickle(f'{file}')


import nltk
from nltk.stem import *
from collections import Counter
import re
from nltk.corpus import stopwords
from nltk.tokenize import RegexpTokenizer
ntlkregtokenizer = RegexpTokenizer(r'\w+')

tokenizer = RegexpTokenizer(r'\w+')

stemmer = PorterStemmer()
topics_removed = []

stopwords = stopwords.words('english')
#stopwords = gensim.parsing.preprocessing.STOPWORDS

def init_ntlk():
    nltk.download('wordnet')
    nltk.download('omw-1.4')

def lemmatize_stemming(text, lem, stem=False):
    if lem:
        lemma = WordNetLemmatizer().lemmatize(text, pos='v') #  The Part Of Speech tag. Valid options are `"n"` for nouns,`"v"` for verbs, `"a"` for adjectives, `"r"` for adverbs and `"s"`for satellite adjectives.
        if stem:
            return stemmer.stem(lemma) 
        else:
            return lemma
    return text

# you can directly match against "token_list", which is a whitelist of allowed to tokens
# Tokenize and lemmatize
def preprocess_text(text, lem=True, min_token_len = 1, stopwords = stopwords, do_composition = False, token_list = None, use_tokenizer='ntlk-regexptokenizer'):
    result = []
    text = str(text)
    global topics_removed

    try:
        if do_composition:
            text = re.sub(r"([a-zA-Z0-9])\-([a-zA-Z0-9])", r"\1\2", text , 0, re.IGNORECASE)
            
        if use_tokenizer == 'ntlk-regexptokenizer':
            tokenized_text = tokenizer.tokenize(text)
        elif use_tokenizer == 'nltk':
            tokenized_text = nltk.tokenize.word_tokenize(text)
        elif use_tokenizer == 'gensim':
            tokenized_text = gensim.utils.simple_preprocess(text)
        
        for token in tokenized_text:
            token = token.lower()
            if token not in stopwords and len(token) >= min_token_len:
                if token_list:
                    ltoken = lemmatize_stemming(token, lem)
                    if ltoken in token_list:
                        result.append(ltoken)
                else:
                    result.append(lemmatize_stemming(token, lem))
            else:
                topics_removed.append(token)
    except Exception as e:
        print(f'Exception on {text}\n{e}')
        return None
            
    return result

from bs4 import BeautifulSoup
from markdown import markdown
import re

def markdown_to_text(markdown_string):
    """ Converts a markdown string to plaintext """

    try:
        # md -> html -> text since BeautifulSoup can extract text cleanly
        html = markdown(markdown_string)

        # remove code snippets
        html = re.sub(r'<pre>(.*?)</pre>', ' ', html)
        html = re.sub(r'<code>(.*?)</code >', ' ', html)

        # extract text
        soup = BeautifulSoup(html, "html.parser")
        text = ''.join(soup.findAll(text=True))
    except Exception as e:
        return markdown_string    

    return text


def clean_text(text):
    #remove @ppl, url
    output = re.sub(r'https://\S*','', text)
    output = re.sub(r'@\S*','',output)
    
    #remove \r, \n
    #rep = r'|'.join((r'\r',r'\n'))
    #output = re.sub(rep,'',output)

    #remove duplicated punctuation
    #output = re.sub(r'([!()\-{};:,<>./?@#$%\^&*_~]){2,}', lambda x: x.group()[0], output)
    
    #remove extra space
    #output = re.sub(r'\s+', ' ', output).strip()
    
    #remove string if string only contains punctuation
    #if sum([i.isalpha() for i in output])== 0:
    #    output = ''
        
    #remove string if length<5
    #if len(output.split()) < 5:
    #    output = ''

    return output

def test_merge(x):
    y = set()
    for x in x:
        if isinstance(x, list):
            y.update(x)
        elif isinstance(x, str):
            y.update(x.split())
        else:
            Exception
    return list(y)

# +
def create_merge(testset, merge_list, merge_to_one=False):
    i=1
    testset_merge = testset
    for merge in merge_list:
        t = from_disk(merge)
        i+=1
        testset_merge = testset_merge.merge(t, on=['name'], suffixes=('', f'_{i}'), how='left')
    
    if(merge_to_one):
        for column in testset.columns[1:]:
            testset_merge[column] = testset_merge[column].apply(lambda x: x.split() if not isinstance(x, list) else x)
            
        y = set()
        testset_merge['topics'] = testset_merge[testset_merge.columns[1:]].apply(
            lambda x: test_merge(x),
            axis=1
        )
        testset_merge.drop(testset_merge.columns[2:], axis=1, inplace=True)
        
    
    return testset_merge


# -

import time
cr_st = 0

def cr_start():
    global cr_st
    cr_st = time.time()

def cr_getrt():
    return time.time() - cr_st


# +
t_set={
    'D_T1': 't1',
    'D_T2': 't1.1',
    'D_T3': 't1.2',
    'D_T4': 't1.3.1',
    'D_T5': 't1.3',
    'D_T6': 't1.4',
    'D_C1': 't2.5.1s+2.5.2+2.5.4+2.5.6+2.5.3',
    'D_C2': 't2.3.1s+2.3.2+2.3.4+2.3.6+2.3.3',
    'D_C3': 't2.4.1s+2.4.2+2.4.4+2.4.6+2.4.3',
}

def t_set_loader(tid, version=3, with_init=False):
    global merge_list
    global t_name
    testav=version
    if tid == 'D_C1':
        merge_list = ["t2.5.2", "t2.5.4", "t2.5.6", "t2.5.3"]
        t_name = 't2.5.1s'
    elif tid == 'D_C2':
        merge_list = ["t2.3.2", "t2.3.4", "t2.3.6", "t2.3.3"]
        t_name = 't2.3.1s'
    elif tid == 'D_C3':
        merge_list = ["t2.4.2", "t2.4.4", "t2.4.6", "t2.4.3"]
        t_name = 't2.4.1s'
    else:
        merge_list = []
        t_name = t_set[tid]
        
    testset = from_disk(f'../testdatav{testav}/{t_name}')
    if len(merge_list) >0:
        t_name = f'{t_name}+{"+".join([re.sub(r"t", "", tid) for tid in merge_list])}'
        print(t_name)
        testset = create_merge(merge_to_one=True, testset=testset, t_name=t_name, merge_list=merge_list)
    if with_init:
        init_short = from_disk('init_short')
        testset = pd.merge(testset, init_short, on="name", how="left")
    
    return testset

