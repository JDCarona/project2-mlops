import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--max_seq_length', dest='max_seq_length', type=int)
args = parser.parse_args()
# do something with pos and opt
print('hello', args.max_seq_length)