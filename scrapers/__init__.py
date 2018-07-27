import os


if os.name == 'nt':
    split = '\\'
else:
    split = '/'

def make_default_path(filename):
    default_output = os.path.dirname(os.path.realpath(__file__)).split(split)
    default_output = default_output[:len(default_output)-1] + ['results', filename]
    return default_output
