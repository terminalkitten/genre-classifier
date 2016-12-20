#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Genre Classifier
#
# Copyright (C) 2016 Juliette Lonij, Koninklijke Bibliotheek -
# National Library of the Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import csv
import re
import sys
import time
import urllib
import utilities

from lxml import etree
from segtok import segmenter

class Article(object):

    url = None
    text = None
    features = {}

    def __init__(self, url=None, text=None):
        self.url = url
        self.text=text
        self.features = self.get_features()


    def get_features(self):
        if self.url:
            print 'Getting features for ' + self.url

        features = {}

        # Get article OCR
        if self.url:
            ocr = self.get_ocr(self.url)
        elif self.text:
            ocr = self.text

        # Remove unwanted characters
        unwanted_chars = [u'|', u'_', u'=', u'(', u')', u'[', u']', u'<',
                u'>', u'#', u'/', u'\\', u'*', u'~', u'`', u'«', u'»',
                u'®', u'^', u'°', u'•', u'★', u'■', u'{', u'}']
        for char in unwanted_chars:
            ocr = ocr.replace(char, '')
            ocr = ' '.join(ocr.split())

        # Find and remove quoted text
        opening_quote_chars = [u'„', u'‚‚', u',,']
        closing_quote_chars = [u'"', u'”', u"'", u'’']

        pattern = ('(^|[^\w])('+ '|'.join(opening_quote_chars +
                closing_quote_chars) + ')(\s\w|\w\w)')
        pattern += ('(?:(?!' + '|'.join(opening_quote_chars +
                ['\s' + c + '\w\w' for c in closing_quote_chars]) +
                ').){0,1000}?')
        pattern += '(' + '|'.join(closing_quote_chars) + ')($|[^\w])'
        pattern = re.compile(pattern, flags=re.UNICODE|re.DOTALL)

        clean_ocr, nr_subs = re.subn(pattern, '', ocr)
        clean_ocr = ' '.join(clean_ocr.split())
        features['direct_quotes'] = nr_subs

        # Count remaining quote chars
        rem_quote_chars = 0
        for char in opening_quote_chars + closing_quote_chars:
            rem_quote_chars += clean_ocr.count(char)
        features['remaining_quote_chars'] = rem_quote_chars

        # Count punctuation
        features['question_marks'] = clean_ocr.count('?')
        features['question_marks_perc'] = (clean_ocr.count('?') /
                float(len(clean_ocr)))
        features['exclamation_marks'] = clean_ocr.count('!')
        features['exclamation_marks_perc'] = (clean_ocr.count('!') /
                float(len(clean_ocr)))
        currency_symbols = 0
        for char in [u'$', u'€', u'£', u'ƒ']:
            currency_symbols += clean_ocr.count(char)
        features['currency_symbols'] = currency_symbols
        features['currency_symbols_perc'] = (currency_symbols /
                float(len(clean_ocr)))
        features['digits'] = len([c for c in clean_ocr if c.isdigit()])
        features['digits_perc'] = (len([c for c in clean_ocr if c.isdigit()]) /
                float(len(clean_ocr)))

        # Sentence chunk cleaned OCR with Segtok
        sentences = [s for s in segmenter.split_single(clean_ocr) if s]
        sentence_count = len(sentences)
        features['sentences'] = sentence_count

        # Chunk, tokenize, tag, lemmatize with Frog
        tokens = self.frog(sentences)

        # Word count
        token_count = len(tokens)
        features['tokens'] = token_count
        features['avg_sentence_length'] = token_count / sentence_count

        # Adjective count and percentage
        adj_count = len([t for t in tokens if t[4].startswith('ADJ')])
        features['adjectives'] = adj_count
        features['adjectives_perc'] = adj_count / float(token_count)

        # Verbs and adverbs count and percentage
        modal_verb_count = len([t for t in tokens if t[4].startswith('WW') and
                t[2].capitalize() in utilities.modal_verbs])
        features['modal_verbs'] = modal_verb_count
        features['modal_verbs_perc'] = modal_verb_count / float(token_count)

        modal_adverb_count = len([t for t in tokens if t[4].startswith('BW') and
                t[2].capitalize() in utilities.modal_adverbs])
        features['modal_adverbs'] = modal_adverb_count
        features['modal_adverbs_perc'] = modal_adverb_count / float(token_count)

        cogn_verb_count = len([t for t in tokens if t[4].startswith('WW') and
                t[2].capitalize() in utilities.cogn_verbs])
        features['cogn_verbs'] = cogn_verb_count
        features['cogn_verbs_perc'] = cogn_verb_count / float(token_count)

        intensifier_count = len([t for t in tokens if t[2].capitalize() in
                utilities.intensifiers])
        features['intensifiers'] = intensifier_count
        features['intensifiers_perc'] = intensifier_count / float(token_count)

        # Personal pronoun counts and percentages
        pronoun_1_count = len([t for t in tokens if t[4].startswith('VNW') and
                t[2] in utilities.pronouns_1])
        pronoun_2_count = len([t for t in tokens if t[4].startswith('VNW') and
                t[2] in utilities.pronouns_2])
        pronoun_3_count = len([t for t in tokens if t[4].startswith('VNW') and
                t[2] in utilities.pronouns_3])
        pronoun_count = pronoun_1_count + pronoun_2_count + pronoun_3_count

        features['pronoun_1'] = pronoun_1_count
        features['pronoun_2'] = pronoun_2_count
        features['pronoun_3'] = pronoun_3_count
        features['pronoun_1_perc'] = pronoun_1_count / float(token_count)
        features['pronoun_2_perc'] = pronoun_2_count / float(token_count)
        features['pronoun_3_perc'] = pronoun_3_count / float(token_count)
        features['pronoun_1_perc_rel'] = (pronoun_1_count / float(pronoun_count)
                if pronoun_count > 0 else 0)
        features['pronoun_2_perc_rel'] = (pronoun_2_count / float(pronoun_count)
                if pronoun_count > 0 else 0)
        features['pronoun_3_perc_rel'] = (pronoun_3_count / float(pronoun_count)
                if pronoun_count > 0 else 0)

        # Named entities
        named_entities = [t for t in tokens if t[6].startswith('B')]

        # NE count
        features['named_entities'] = len(named_entities)
        features['named_entities_perc'] = (len(named_entities) /
                float(token_count))

        # NE position
        features['named_entities_pos'] = ((sum([tokens.index(t) for t in
                named_entities]) / float(len(named_entities))) /
                float(token_count)) if len(named_entities) else 0

        # Unique named entities
        unique_ne_strings = []
        ne_strings = set([t[1].lower() for t in named_entities])
        for ne_source in ne_strings:
            unique = True
            for ne_target in [n for n in ne_strings if n != ne_source]:
                if ne_target.find(ne_source) > -1:
                    unique = False
                    break
            if unique:
                unique_ne_strings.append(ne_source)

        features['unique_named_entities'] = (len(unique_ne_strings) /
                float(len(named_entities))) if len(named_entities) else 0

        # Self classification
        lemmas = [t[2].lower() for t in tokens]
        for cl in utilities.self_classifications:
            feature_name = 'self_cl_' + cl
            features[feature_name] = 0
            for w in utilities.self_classifications[cl]:
                if w in lemmas:
                    features[feature_name] += 1

        return features


    def get_ocr(self, url):
        ocr = ''
        while not ocr:
            data = urllib.urlopen(self.url).read()
            data = data.replace('</title>', '.</title>')
            xml = etree.fromstring(data)
            ocr = etree.tostring(xml, encoding='utf8',
                    method='text').decode('utf-8')
            if not ocr:
                time.sleep(5)
                print 'OCR not found, retrying ...'
        print('OCR found: ' + ' '.join(ocr.split())[:50] + ' ...')
        return ocr


    def frog(self, sentences):

        frog_url = 'http://www.kbresearch.nl/frogger/?'

        tokens = []

        to_frog = sentences
        while len(to_frog):
            batch_size = 1 if len(to_frog) >= 1 else len(to_frog)
            batch = ' '.join(to_frog[:batch_size]).encode('utf-8')
            #print batch + '\n'

            query_string = urllib.urlencode({'text': batch})

            data = ''
            i = 0
            while not data:
                try:
                    data = urllib.urlopen(frog_url + query_string).read()
                    data = data.decode('utf-8')
                except IOError:
                    if i < 2:
                        print('Frog data not found, retrying ...')
                        self.frog_log('Frog data not found, retrying ...')
                        time.sleep(5)
                        i += 1
                    else:
                        print('Frog data not found, skipping!')
                        self.frog_log('Frog data not found, skipping!')
                        raise

            lines = [l.split('\t') for l in data.split('\n') if l]
            try:
                assert len(lines[0]) == 10, 'Frog data invalid: ' + ' '.join(data.split())
            except AssertionError as e:
                self.frog_log('Frog data invalid: ' + ' '.join(data.split()))
                raise

            tokens += [l for l in lines if len(l) == 10]
            to_frog = to_frog[batch_size:]

        return tokens


    def frog_log(self, message):
        with open ('frog_log.txt', 'a') as f:
            f.write(self.url + ' | ' + message + '\n')


if __name__ == '__main__':
    url = 'http://resolver.kb.nl/resolve?urn=KBNRC01:000028060:mpeg21:a0154:ocr'
    art = Article(url=url)

