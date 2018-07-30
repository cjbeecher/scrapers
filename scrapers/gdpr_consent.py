import json
import requests
from base64 import urlsafe_b64decode
from base64 import urlsafe_b64encode


vendor_lists = {}


class ValueTracker:

    def __init__(self, array):
        self.array = array
        self.value = 0
        self.current = 0
        self.index = 0
        self.reset()

    def reset(self):
        self.value = 0
        self.current = 0
        self.index = 0

    def get_bits(self, count):
        iter_count = 0
        while self.current < count:
            self.value = (self.value << 8) + self.array[self.index]
            self.index += 1
            self.current += 8
            iter_count += 1
        diff = self.current - count
        out = int(self.value >> diff)
        self.current = diff
        if type(diff) == float:
            raise ValueError
        self.value = int(self.value) & int((2 ** diff) - 1)
        return out


def get_vendor_list(version):
    global vendor_lists
    url = 'https://vendorlist.consensu.org/v-{version}/vendorlist.json'
    try:
        return vendor_lists[version]
    except KeyError as err:
        res = requests.get(url.format(version=version)).text
        try:
            vendor_lists[version] = json.loads(res)
        except json.decoder.JSONDecodeError as j_err:
            vendor_lists[version] = None
        return vendor_lists[version]


def decode(x):
    x = x.encode('utf-8')
    miss = 3 - len(x) % 3
    x = x + b''.join([b'='] * miss)
    x = urlsafe_b64decode(x)
    return x


def parse(x):
    output = {}
    tracker = ValueTracker(x)
    try:
        output['version'] = tracker.get_bits(6)
        output['created'] = tracker.get_bits(36) / 10  # datetime.fromtimestamp(tracker.get_bits(36) / 10)
        output['updated'] = tracker.get_bits(36) / 10  # datetime.fromtimestamp(tracker.get_bits(36) / 10)
        output['cmpid'] = tracker.get_bits(12)
        output['cmpversion'] = tracker.get_bits(12)
        output['consentscreen'] = tracker.get_bits(6)
        tmp = []
        tmp.append(int(tracker.get_bits(6)) + 65)
        tmp.append(int(tracker.get_bits(6)) + 65)
        output['consentlanguage'] = bytes(tmp).decode('utf-8')
        output['vendorlistversion'] = tracker.get_bits(12)
        tmp = int(tracker.get_bits(24))
        output['purposesallowed'] = []
        exp = 2 ** 23
        pid = 1
        while exp > 0:
            if tmp & exp > 0:
                output['purposesallowed'].append(pid)
            pid += 1
            exp = int(exp >> 1)
        output['maxvendorid'] = int(tracker.get_bits(16))
        output['encodingtype'] = int(tracker.get_bits(1))
        if output['encodingtype'] == 0:
            output['bitfieldsection'] = {}
            section = output['bitfieldsection']
            section['bitfield'] = []
            for i in range(output['maxvendorid']):
                try:
                    tmp = tracker.get_bits(1)
                    if tmp > 0:
                        section['bitfield'].append(i+1)
                except IndexError as err:
                    break
        else:
            output['rangesection'] = {}
            section = output['rangesection']
            section['defaultconsent'] = int(tracker.get_bits(1))
            entries = int(tracker.get_bits(12))
            section['numentries'] = entries
            section['vendors'] = []
            for i in range(entries):
                tmp = {}
                tmp['single'] = int(tracker.get_bits(1))
                if tmp['single'] == 0:
                    tmp['vendor'] = int(tracker.get_bits(16))
                else:
                    tmp['start'] = int(tracker.get_bits(16))
                    tmp['end'] = int(tracker.get_bits(16))
                section['vendors'].append(tmp)
    except IndexError as err:
        output['purposesallowed'] = [] if 'purposesallowed' not in output else output['purposesallowed']
    return output


def run(strings):
    data = [{'consent': decode(i)} for i in strings]
    for i in data:
        i['parsed'] = parse(i['consent'])
        i['consent'] = urlsafe_b64encode(i['consent']).decode('utf-8').replace('=', '')
        # TODO: get vendor ID list and replace IDs with readable vendor names
        # vendors = get_vendor_list(i['vendorlistversion'])
    return data


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--consent', nargs='*')
    args = parser.parse_args()
    output = run(args.consent)
    print(output[0])
