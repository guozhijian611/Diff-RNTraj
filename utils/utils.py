import pickle
import json
import random
import os
import numpy as np


def _build_path(dir_path, file_name):
    return os.path.join(dir_path, file_name)


def create_dir(directory):
    """
    Creates a directory if it does not already exist.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)


def save_pkl_data(data, dir, file_name):
    create_dir(dir)
    pickle.dump(data, open(_build_path(dir, file_name), 'wb'))


def load_pkl_data(dir, file_name):
    '''
    Args:
    -----
        path: path
        filename: file name
    Returns:
    --------
        data: loaded data
    '''
    file = open(_build_path(dir, file_name), 'rb')
    data = pickle.load(file)
    file.close()
    return data


def save_json_data(data, dir, file_name):
    create_dir(dir)
    with open(_build_path(dir, file_name), 'w') as fp:
        json.dump(data, fp)


def load_json_data(dir, file_name):
    with open(_build_path(dir, file_name), 'r') as fp:
        data = json.load(fp)
    return data
