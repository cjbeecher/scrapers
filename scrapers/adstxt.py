import requests
import multiprocessing
from datetime import datetime


MAX_QUEUE_SIZE = 100000
INPUT_QUEUE = multiprocessing.JoinableQueue(MAX_QUEUE_SIZE)
OUTPUT_QUEUE = multiprocessing.JoinableQueue(MAX_QUEUE_SIZE)


def scan_domains(input_queue, output_queue):
    pass


def run(output, domains=None, input_file=None, processes_count=2):
    """
    Processes the list of domains for an ads.txt file
    :param output: Where to store the results
    :param domains: List of domains to process
    :param input_file: New line delimited file with domains to process
    :return:
    """
    if input_file is None and (domains is None or len(domains) == 0):
        raise ValueError('No input specified (no domains or input file)')
    if not isinstance(output, str):
        raise ValueError('No output file specified')
    if domains is None:
        with open(input_file, 'r') as f:
            domains = [i.strip() for i in f.read().split('\n')]
    processes = []
    for i in range(processes_count):
        process = multiprocessing.Process()
    for domain in domains:
        INPUT_QUEUE.put(domain)


if __name__ == '__main__':
    import argparse
    import scrapers
    parser = argparse.ArgumentParser()
    default_output = 'adstxt_results_{0}.csv'.format(datetime.now().strftime('%Y-%m-%dT%H'))
    parser.add_argument('--domains', type=str, nargs='*', help='List of domains to scan')
    parser.add_argument('--input_file', type=str, nargs='*', help='New line delimited file with domains to scan')
    parser.add_argument('--output', type=str, default=scrapers.make_default_path(default_output), help='Output file')
    parser.add_argument('--processes', type=int, default=2, help='Number of subprocesses to create for domains processing')
    args = parser.parse_args()
    run(args.output, domains=args.domains, input_file=args.input_file, processes=args.processes)
