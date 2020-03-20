import re
import os
import spacy
import xml.etree.ElementTree as ET
from spacy.lang.ru import Russian
from spacy_russian_tokenizer import RussianTokenizer, MERGE_PATTERNS
import time
from pymystem3 import Mystem
from string import punctuation

# import ru2e

spacy.prefer_gpu()


def regTokenize(text):
    """
    вроде как быстрый токенизатор?
    :param text:
    :return:
    """
    WORD = re.compile(r'\w+')
    words = WORD.findall(text)
    # return ' '.join(words)
    return words


def myany(text: list, vocab: list):
    """
    проверка на наличие слов из словаря в строке
    """

    for word in text:
        if word in vocab:
            return True
    return False


def mystem_tokenizer(text):
    """
    токенизатор на основе mystem
    :param text:
    :return:
    """

    mystem = Mystem()
    tokens = mystem.lemmatize(text.lower())
    punc_list = ' –!"@#$%^&*()*+_,.\:;<>=?[]{}|~`/«»—' + '0123456789'
    tokens = [token for token in tokens if token != " " and token.strip() not in set(punctuation + punc_list)]

    # return tokens
    return ' '.join(tokens)


def spacy_tokenizer(text, lemm: bool):
    """токенизатор на основе библиотеки spacy, учитывающий особенности русского языка
    spacy_russian_tokenizer --- токенизация
    spacy_ru2 --- лемматизация (как параметр)
    стоп слова?
    не всегда правильно работает (часто плохие леммы), надо разбираться -
    в репо написано использовать ru2e, но не работает
    """

    # nlp = spacy.load('/media/anton/ssd2/data/datasets/spacy-ru/ru2')
    # # nlp = spacy.load('ru2', disable=['tagger', 'parser', 'NER'])
    # nlp.add_pipe(nlp.create_pipe('sentencizer'), first=True)
    # doc = nlp(text)

    # ВЗЯТЬ РУССКИЙ ТОКЕНИЗАТОР https://github.com/antongolubev5/spacy_russian_tokenizer
    nlp = Russian()
    russian_tokenizer = RussianTokenizer(nlp, MERGE_PATTERNS)
    nlp.add_pipe(russian_tokenizer, name='russian_tokenizer')
    doc = nlp(text)

    text = [token.lemma_ for token in doc] if lemm else text

    punc_list = set(' –!"@#$%^&*()*+_,.\:;<>=?[]{}|~`/«»—' + '0123456789')
    output = []

    for i in range(len(text)):
        text[i] = re.sub(" +", " ", text[i])
        text[i] = text[i].lower()
        if not (text[i] in punc_list):
            output.append(text[i])

    return output


def mkdir_labeled_texts(directory_path, corpus_name, new_dir_name):
    """создание папки, в которую будем добавлять размеченные тексты"""
    for month in os.listdir(os.path.join(directory_path, corpus_name)):
        for day in os.listdir(os.path.join(directory_path, corpus_name, month)):
            for utf in os.listdir(os.path.join(directory_path, corpus_name, month, day)):
                os.mkdir(os.path.join(directory_path, corpus_name, month, day, utf, new_dir_name))


def searching_entities_in_corpus(directory_path, corpus_name, entities_with_sentiments):
    """
    поиск тональных сущностей в текстах.
    сущности = размеченные pos/neg слова из русентилекс
    каждый файл из папки разметить и перекинуть в labeles_texts с соотв названием файла + labeled
    :return:
    :param directory_path:
    :param corpus_name:
    :param entities_with_sentiments: словарь тональных слов
    """

    for month in os.listdir(os.path.join(directory_path, corpus_name)):
        for day in os.listdir(os.path.join(directory_path, corpus_name, month)):
            for utf in os.listdir(os.path.join(directory_path, corpus_name, month, day)):
                for text_file in os.listdir(os.path.join(directory_path, corpus_name, month, day, utf, 'items')):
                    tree = ET.parse(
                        os.path.join(os.path.join(directory_path, corpus_name, month, day, utf, 'items', text_file)))
                    text = tree.getroot()[0].text
                    f = open(os.path.join(directory_path, corpus_name, month, day, utf, 'labeled_items',
                                          text_file[:-4] + '_labeled.txt'), "w")
                    f.write(text + '\n')
                    f.write('\n')
                    text = spacy_tokenizer(text, True)
                    f.write('ТОНАЛЬНЫЕ СЛОВА: ' + '\n')
                    for word in text:
                        if word in entities_with_sentiments.keys():
                            f.write(word + ' : ' + entities_with_sentiments[word] + '\n')

                    f.write('\n')
                    f.write('НЕТОНАЛЬНЫЕ СЛОВА: ' + '\n')
                    for word in text:
                        if not (word in entities_with_sentiments.keys()):
                            f.write(word + '\n')
                    f.close()


def creating_entities_vocab(directory_path, files: list):
    """
    выделение из словаря русентилекс тональных слов (positive/negative)
    :param directory_path: путь к файлам
    :param files: список файлов, из которых необходимо достать слова
    :return: словарь тональных слов
    """

    entities_with_sentiments = {}

    for i in range(len(files)):
        files[i] = open(os.path.join(directory_path, files[i]), 'r')

    for file in files:
        for line in file:
            line_info = line.strip().split(', ')
            word = line_info[0]
            if not (word in entities_with_sentiments.keys()):
                entities_with_sentiments[word] = line_info[3]
        file.close()

    return entities_with_sentiments


def searching_contexts_by_entities(directory_path, corpus_name, entities_vocab: dict, nlp, month, output_file):
    """
    по имеющимся сущностям набираем из корпуса выборку контекстов
    :param nlp: модель для разбиения текста на предложения
    :param entities_vocab:
    :param directory_path:
    :param corpus_name:
    :return:
    """

    contexts_for_entities = open(os.path.join(directory_path, output_file), 'w')
    list_entities_vocab_keys = list(entities_vocab.keys())

    # пробегаем по всем текстам корпуса и выискиваем предложения, содержащие размеченные слова из словаря
    # for month in os.listdir(os.path.join(directory_path, corpus_name)):
    # month = '201101'
    for day in os.listdir(os.path.join(directory_path, corpus_name, month)):
        for utf in os.listdir(os.path.join(directory_path, corpus_name, month, day)):
            if len(os.listdir(os.path.join(directory_path, corpus_name, month, day, utf))) > 0:
                for item in os.listdir(os.path.join(directory_path, corpus_name, month, day, utf, 'items')):
                    tree = ET.parse(
                        os.path.join(os.path.join(directory_path, corpus_name, month, day, utf, 'items', item)))
                    text = tree.getroot()[0].text
                    # text_tok = spacy_tokenizer(text, True)
                    # text_tok = mystem_tokenizer(text)
                    # if any(word in list_entities_vocab_keys for word in text_tok):
                    #     print(text)
                    print(text)
                    contexts_for_entities.write(text + '\n')
                for text in os.listdir(os.path.join(directory_path, corpus_name, month, day, utf, 'texts')):
                    f = open(os.path.join(directory_path, corpus_name, month, day, utf, 'texts', text), 'r')
                    # sent_tok = spacy_tokenizer(sent, True)
                    # sent_tok = mystem_tokenizer(sent)
                    # if any(word in list_entities_vocab_keys for word in sent_tok):
                    #     print(sent)
                    # contexts_for_entities.write(sent+'\n')
                    for sent in text2sentences(f.read(), nlp):
                        contexts_for_entities.write(sent + '\n')
                        print(sent)
                    f.close()

    contexts_for_entities.close()


def searching_personal_entities(directory_path, file_from, file_to):
    """
    поиск сущностей, которыми можно охарактеризовать людей и запись их в другой файл
    :param directory_path: путь до файлов
    :param file_from: откуда брать сущности
    :param file_to: куда перекладывать сущности
    :return:
    """

    file_from = open(os.path.join(directory_path, file_from), 'r+')
    file_to = open(os.path.join(directory_path, file_to), 'w')

    for line in file_from:
        print(line.strip())
        if input() == 'y':
            file_to.write(line)


def text2sentences(text, nlp):
    """
    разделение текста на предложения
    """

    # nlp = spacy.load('/media/anton/ssd2/data/datasets/spacy-ru/ru2')
    # nlp.add_pipe(nlp.create_pipe('sentencizer'), first=True)
    doc = nlp(text)
    sentences = [sent.string.strip() for sent in doc.sents]

    return sentences


def searching_contexts(directory_path, entities_vocabs: list, sentences_file, contexts_file, sentence_volume):
    """
    поиск тональных контекстов cреди предложений корпуса
    :param directory_path:
    :param entities_vocabs: список из названий файлов, в которых лежат тональные слова
    :param sentences_file: файл с предложениями из корпуса
    :param contexts_file: файл, в который будут записаны контексты
    :param sentence_volume: сколько предложений из корпуса рассматривать [0:vol]
    """

    vocab = {}
    vocab_neg = open(os.path.join(directory_path, entities_vocabs[0]), 'r')
    vocab_pos = open(os.path.join(directory_path, entities_vocabs[1]), 'r')

    for line in vocab_pos:
        line_info = line.split(', ')
        vocab[line_info[0]] = line_info[3]

    for line in vocab_neg:
        line_info = line.split(', ')
        vocab[line_info[0]] = line_info[3]

    list_entities_vocab_keys = list(vocab.keys())
    contexts = open(os.path.join(directory_path, contexts_file), 'w')
    cnt = 0

    with open(os.path.join(directory_path, sentences_file), 'r') as corpus_sentences:
        firstNlines = corpus_sentences.readlines()

    cnt = 1

    for line in firstNlines:
        print(cnt, '/', len(firstNlines), ' = ', round(cnt / len(firstNlines) * 100, 2), '%...')
        line_tok = spacy_tokenizer(line, True)
        if any(word in list_entities_vocab_keys for word in line_tok):
            cnt += 1
            contexts.write(line.strip() + '===' + ' '.join(line_tok))
            print(cnt, line.strip() + '===' + ' '.join(line_tok))
        cnt += 1

    for file in [vocab_neg, vocab_pos, contexts, corpus_sentences]:
        file.close()


def check_tones(text: list, vocab: dict):
    """
    определение тональности предложения
    отбрасывание мультитональных предложений
    вывод тональных слов
    1 = good, -1 = bad, 0 = mixed, -10 = trash
    """

    bad = False
    good = False
    bad_words = []
    good_words = []

    for word in text:
        if word in vocab.keys():
            if vocab[word] == 'positive':
                good = True
                if word not in good_words:
                    good_words.append(word)
            else:
                bad = True
                if word not in bad_words:
                    bad_words.append(word)
            if good and bad:
                return 0, good_words + bad_words

    if good:
        return 1, good_words

    if bad:
        return -1, bad_words

    return -10, []


def divide_contexts(directory_path, entities_vocab, contexts, positive_contexts, negative_contexts):
    """
    разделение имеющихся контекстов на 2 позитивные и негативные
    смешанные контексты выбрасываются
    :param directory_path: путь
    :param entities_vocab: словарь тональных сущностей
    :param contexts: имя файла, в котором лежат все контексты
    :param positive_contexts: имя файла, в который записываем + контексты
    :param negative_contexts: имя файла, в который записываем - контексты
    :return:
    """

    positive_contexts = open(os.path.join(directory_path, positive_contexts), 'w')
    negative_contexts = open(os.path.join(directory_path, negative_contexts), 'w')
    cnt = 1

    with open(os.path.join(directory_path, contexts), 'r') as contexts:
        contexts_lines = contexts.readlines()

    for line in contexts_lines:
        print(cnt, '/', len(contexts_lines), ' = ', round(cnt / len(contexts_lines) * 100, 2), '%...')
        line_text = line.split('===')[0]
        line_tok = line.split('===')[1].strip()
        flag, lst = check_tones(line_tok.split(" "), entities_vocab)

        if flag == 1:
            positive_contexts.write(line_text + '===' + line_tok + '===' + ' '.join(lst) + '===' + '1' + '\n')
        elif flag == -1:
            negative_contexts.write(line_text + '===' + line_tok + '===' + ' '.join(lst) + '===' + '-1' + '\n')
        else:
            print(line_text)

        cnt += 1

    for file in [contexts, positive_contexts, negative_contexts]:
        file.close()


def main():
    start_time = time.time()

    directory_path = '/media/anton/ssd2/data/datasets/aspect-based-sentiment-analysis'
    corpus_name = 'Rambler_source'

    total_time = round((time.time() - start_time))
    print("Time elapsed: %s minutes %s seconds" % ((total_time // 60), round(total_time % 60)))


if __name__ == '__main__':
    main()
