import argparse, logging, sys, os, time
from utils import dataprep as dp
from datasource.data import DataSet
from sklearn.model_selection import StratifiedShuffleSplit
import numpy as np



def process_args(args) :
    '''
    Parses the commandline arguments
    :param args: the commandline arguments
    :return: parsed args
    '''

    parser = argparse.ArgumentParser()

    parser.add_argument('--name',
                        type = str, default = 'of_model',
                        help = ('Name of the '
                                'dataset'))

    parser.add_argument('--batch_size',
                        type = int, default = 10,
                        help = ('number of batches  to use for generating '
                                'sequences'))

    parser.add_argument('--print_every',
                        type = int, default = 100,
                        help = ('interval to print status in to give a sense '
                                'of progress'))

    parser.add_argument('--root_dir',
                        type = str, default = '/tmp',
                        help = ('Root directory of '
                                'the raw data'))
    parser.add_argument('--log_dir',
                        type = str, default = '/tmp',
                        help = ('Directory to dump '
                                'log files'))

    parser.add_argument('--min_len', type = int, default = 1,
                        help = ('Min sequence length'))

    parser.add_argument('--max_len', type = int, default = 5,
                        help = ('max sequence length'))

    parser.add_argument('--n_seq', type = int, default = 500,
                        help = ('Number of '
                                'sequences to '
                                'generate'))

    parser.add_argument('--output_dir',
                        type = str, default = '/tmp',
                        help = ('directory location '
                                'to output the '
                                'training and testing '
                                'instances'))

    parser.add_argument('--train_size',
                        type = float, default = 0.7,
                        help = ('proportion of the '
                                'total number of '
                                'sequences to keep '
                                'for training and the '
                                'rest will be for '
                                'testing. For eg, 0.7'))
    parameters = parser.parse_args(args)
    return parameters


def initialize_logger(log_dir) :
    '''
    This initializes the logger
    :param log_dir: Path to the log file
    :return:
    '''
    logging.basicConfig(
        level = logging.DEBUG,
        format = '%(asctime)-15s %(name)-5s %(levelname)-8s %('
                 'message)s',
        filename = log_dir)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)-15s %(name)-5s %(levelname)-8s %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)


def dump_sequences(dir, data_seqs, lbl_seqs, print_every=100) :
    '''
    Dumps the data sequences into a
    :param dir: dir to dump data
    :param data_seqs: data sequences
    :param lbl_seqs: label sequences
    :return: satus (True / False)
    '''
    #create directory if does not exist
    data_dir = os.path.join(dir, 'data')
    file_list_f = os.path.join(dir, 'dataset.txt')
    if not os.path.exists(data_dir) :
        os.makedirs(data_dir)

    file_list = []
    for i, (lbl, data) in enumerate(zip(lbl_seqs, data_seqs)):
        lbl_str = ''.join(lbl)
        data_file_name = str(time.time())+ '_' +str(i) + '_' + lbl_str
        file_save_path = os.path.join(data_dir, data_file_name)
        if i % print_every == 0 :
            logging.info('dumping ' + ''.join(lbl) + ' into ' +
                         file_save_path)

        np.save(file_save_path, data)

        with open(file_list_f, "a") as myfile :
            myfile.write(data_file_name + '.npy ' + lbl_str + ' ' +
                         str(data.shape[0]) + ' ' + str(len(lbl_str)) + '\n')

    return False


def generator(args) :
    '''
    Generates random data sequences
    :param args: commandline args
    :return:
    '''

    # Parsed commandline args
    parameters = process_args(args)

    # Some boilerplate code for logging and stuff
    initialize_logger(parameters.log_dir)

    labels, data, target, labelsdict, avg_len_emg, avg_len_acc, \
    user_map, user_list, data_dict, max_length_emg, max_length_others, \
    data_path, codebook = dp.getTrainingData(parameters.root_dir)

    # Number of instances per sequence length
    inst_per_batch = parameters.n_seq / parameters.batch_size

    g_max_len = 0
    g_min_len = 100000000
    g_avg_len = 0.0
    n_train = 0
    n_test = 0

    for batch in range(parameters.batch_size):
        logging.info('Generating data for batch' + str(batch+1))
        n_instances_per_seq_len = (inst_per_batch / (parameters.max_len -
                                                       parameters.min_len + 1))

        label_seqs, label_seq_lengths = dp.generate_label_sequences(labels,
                                                            n_instances_per_seq_len,
                                                            l_range = (parameters.min_len, parameters.max_len),
                                                            print_every=parameters.print_every)

        data_seqs, t_data_seq, avg_len, min_len, max_len = dp.generate_data_sequences(codebook,
                                                           label_seqs,
                                                           print_every=parameters.print_every)
        sss = StratifiedShuffleSplit(n_splits = 1,
                                     #test_size = (1 - parameters.train_size),
                                     train_size = parameters.train_size,
                                     random_state = 0)

        train_idx = []
        test_idx = []

        for train_index, test_index in sss.split(np.zeros(len(label_seq_lengths)),
                                                 label_seq_lengths) :
            train_idx = train_index
            test_idx = test_index

        train_x, train_y, test_x, test_y = dp.splitDataset(train_idx, test_idx,
                                                           label_seqs, data_seqs)

        dataset_root_dir = os.path.join(parameters.output_dir, parameters.name)
        #dump training data
        dump_sequences(os.path.join(dataset_root_dir, 'training'),
                       train_x,
                       train_y,
                       print_every = parameters.print_every)

        # dump testing data
        dump_sequences(os.path.join(dataset_root_dir, 'testing'),
                       test_x,
                       test_y,
                       print_every = parameters.print_every)

        g_avg_len = g_avg_len + avg_len
        g_max_len = max(g_max_len, max_len)
        g_min_len = min(g_min_len, min_len)
        n_train += train_y.shape[0]
        n_test += test_y.shape[0]

        with open(os.path.join(dataset_root_dir, 'meta.txt'), "w") as myfile :
            myfile.write('name : ' +  parameters.name + '\n' +
                         'avg_len : ' + str(g_avg_len/(batch+1))+ '\n' +
                         'min_len : ' + str(g_min_len) + '\n' +
                         'max_len : ' + str(g_max_len) + '\n' +
                         'training instances : ' + str(n_train) + '\n' +
                         'testing instances : ' + str(n_test) + '\n')

    logging.info('Finished generating dataset ' + parameters.name)

if __name__ == '__main__' :
    generator(sys.argv[1 :])
