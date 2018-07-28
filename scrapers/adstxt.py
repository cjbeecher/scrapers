import re
import json
import queue
import redis
import requests
import multiprocessing
from io import StringIO
from datetime import datetime


URL = 'http://{0}/ads.txt'
COMMENTS = re.compile('#.*?$', re.M)
SUBDOMAINS = re.compile('subdomain *=(.*?)$')
COMPLETE_KEY = 'adstxt_complete'
HTML = re.compile('<.*?html|<.*?\?.*?xml|<.*?script|<.*?meta|<.*?head', re.I)


def verify_is_adstxt(adstxt):
    if adstxt is None:
        return None
    m = HTML.search(adstxt)
    if m is None:
        return adstxt
    else:
        return None


def get_adstxt_file(domain):
    try:
        err = None
        adstxt = requests.get(
            URL.format(domain),
            allow_redirects=True,
            timeout=10
        ).text
    except Exception as exc:
        err = type(exc).__name__
        adstxt = None
    finally:
        output = {
            'adstxt': verify_is_adstxt(adstxt),
            'error': err
        }
    return output


def parse_adstxt(data):
    adstxt = data['adstxt']
    data['parsed'] = {}
    data['parsed']['subdomains'] = []
    data['parsed']['entries'] = []
    if not isinstance(adstxt, str):
        return None
    adstxt = COMMENTS.sub('', adstxt)
    adstxt = [i.strip() for i in adstxt.split('\n')]
    subdomains = [SUBDOMAINS.search(i) for i in adstxt]
    subdomains = [i.group(1) for i in subdomains if i is not None and i.group(1) != '']
    entries = [i.split(',') for i in adstxt]
    entries = [[z.strip() for z in i] for i in entries if len(i) > 2]
    data['parsed']['subdomains'] = subdomains
    data['parsed']['entries'] = [
        {
            'domain': i[0],
            'publisher': i[1],
            'type': i[2],
            'certificate_id': None if len(i) < 4 else i[3]
        }
        for i in entries
    ]


def write_to_file(output_file, output_queue, keep_raw=False):
    time = 15
    batch = 10000
    tmp = StringIO()
    current = 0
    while True:
        try:
            data = output_queue.get(True, time)
        except queue.Empty:
            break
        if not keep_raw:
            del data['adstxt']
        data = json.dumps(data)
        tmp.write(data + '\n')
        output_queue.task_done()
        current += 1
        if current == batch:
            tmp.seek(0)
            with open(output_file, 'a') as f:
                f.write(tmp.read())
            tmp = StringIO()
            current = 0
    if current > 0:
        tmp.seek(0)
        with open(output_file, 'a') as f:
            f.write(tmp.read())
    return


def scan_domains(input_queue, output_queue):
    """
    Scan domains in the queue for adstxt
    :param input_queue: Input domain queue
    :param output_queue: Results queue for writing to file
    :return:
    """
    processed = redis.Redis()
    while True:
        try:
            domain = input_queue.get(True, 3).strip()
            if processed.sismember(COMPLETE_KEY, domain):
                input_queue.task_done()
                continue
        except queue.Empty:
            break
        data = get_adstxt_file(domain)
        data['domain'] = domain
        parse_adstxt(data)
        processed.sadd(COMPLETE_KEY, domain)
        input_queue.task_done()
        for subdomain in data['parsed']['subdomains']:
            if not processed.sismember(COMPLETE_KEY, subdomain):
                input_queue.put(subdomain)
        output_queue.put(data)


def run(output, domains=None, input_file=None, keep_raw=False, process_count=2):
    """
    Processes the list of domains for an ads.txt file
    :param output: Where to store the results
    :param domains: List of domains to process
    :param input_file: New line delimited file with domains to process
    :param keep_raw: Keep raw results after processing
    :param process_count: Number of processes to spawn
    :return:
    """
    input_queue = multiprocessing.JoinableQueue()
    output_queue = multiprocessing.JoinableQueue()
    if input_file is None and (domains is None or len(domains) == 0):
        raise ValueError('No input specified (no domains or input file)')
    if not isinstance(output, str):
        raise ValueError('No output file specified')
    if domains is None:
        with open(input_file, 'r') as f:
            domains = [i.strip() for i in f.read().split('\n')]
    processed = redis.Redis()
    processed.delete(COMPLETE_KEY)
    processes = []
    for i in range(process_count):
        process = multiprocessing.Process(target=scan_domains, args=(input_queue, output_queue,))
        process.start()
        processes.append(process)
    writer = multiprocessing.Process(target=write_to_file, args=(output, output_queue,), kwargs={'keep_raw': keep_raw})
    writer.start()
    for domain in domains:
        input_queue.put(domain)
    input_queue.join()
    output_queue.join()
    writer.join()
    processed.delete(COMPLETE_KEY)


if __name__ == '__main__':
    import argparse
    import scrapers
    parser = argparse.ArgumentParser()
    default_output = 'adstxt_results_{0}.json'.format(datetime.now().strftime('%Y-%m-%dT%H'))
    parser.add_argument('--domains', type=str, nargs='*', help='List of domains to scan')
    parser.add_argument('--input_file', type=str, nargs='*', help='New line delimited file with domains to scan')
    parser.add_argument('--output', type=str, default=scrapers.make_default_path(default_output), help='Output file')
    parser.add_argument('--processes', type=int, default=2, help='Number of subprocesses to create for domains processing')
    parser.add_argument('--keep_raw', type=bool, nargs='?', default=False, const=True, help='Keep raw results after processing')
    args = parser.parse_args()
    run(args.output, domains=args.domains, input_file=args.input_file, keep_raw=args.keep_raw, process_count=args.processes)
