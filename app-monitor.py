import argparse
import json
import urllib2
import socket
import sys
import Queue
from threading import Thread
from urlparse import urlparse


'''
A test harness to query multiple endpoints and roll up monitoring errors
into a single alert for Nagios
'''

# TODO
# add parameters for default contact
# and default alert level
# if there is an unknown error, use those.

# default argument values
MAX_THREADS = 10
DEFAULT_TIMEOUT = 30  # seconds
MAX_OUTPUT_LEN = 250

# exit status codes/messages
EXIT_OK = (0, 'OK')
EXIT_WARNING = (1, 'WARNING')
EXIT_CRITICAL = (2, 'CRITICAL')

# endpoint levels
LEVELS = {
    'critical': EXIT_CRITICAL,
    'warning': EXIT_WARNING,
    'ok': EXIT_OK
}

# metadata errors
CONFIG_ERROR = 'Metadata error'
CONFIG_ERROR_SCHEMA = 'Improper metadata format'
CONFIG_ERROR_JSON_REQUEST = 'Cannot download metadata'
CONFIG_ERROR_JSON_PARSE = 'Cannot parse metadata'

# usage errors
PARAM_ERROR_MEATADATA_URL = 'Invalid metadata URL'


class TestHarness:
    '''
    Runs application monitoring endpoint tests.
    '''

    def __init__(self, metadata_url, default_contact, default_level, max_threads, timeout, max_output_len):

        # the default level for metadata errors
        self.default_level = default_level
        # the default contact for metadata errors
        self.default_contact = default_contact
        # a queue of all the endpoints to process
        self.endpoints = Queue.Queue()
        # the maximum number of threads
        self.max_threads = max_threads
        # the metadata object
        self.metadata = None
        # the metadata URL
        self.metadata_url = metadata_url
        # max output length
        self.max_output_len = max_output_len
        # a queue of the endpoint results
        self.results = Queue.Queue()
        # the metadata tag
        self.tag = default_contact
        # the default timeout for network requests
        self.timeout = timeout

    def run(self):

        # parse the metadata URL for its base URL
        try:
            parsed = urlparse(self.metadata_url)
        except:
            self.default_contact = 'monitoring'
            self.halt_config_error(PARAM_ERROR_MEATADATA_URL)
        if parsed.scheme == '' or parsed.netloc == '':
            self.default_contact = 'monitoring'
            self.halt_config_error(PARAM_ERROR_MEATADATA_URL)
        base_url = parsed.scheme + '://' + parsed.netloc

        # fetch the metadata
        try:
            req = urllib2.Request(url=self.metadata_url)
            f = urllib2.urlopen(req, timeout=self.timeout)
            response = f.read()
        except Exception:
            self.halt_config_error(CONFIG_ERROR_JSON_REQUEST)
        try:
            metadata = json.loads(response)
        except:
            self.halt_config_error(CONFIG_ERROR_JSON_PARSE)

        # parse metadata
        try:
            self.tag = metadata['tag']
            # prepend base URL to each endpoint,
            # validate each endpoint configuration
            # and queue the endpoints for the worker threads
            endpoints = metadata['endpoints']
            for endpoint in metadata["endpoints"]:
                if 'name' not in endpoint \
                        or 'level' not in endpoint \
                        or endpoint['level'] not in LEVELS:
                    raise Exception
                endpoint['url'] = base_url + endpoint['url']
                self.endpoints.put(endpoint)
        except:
            self.halt_config_error(CONFIG_ERROR_SCHEMA)

        # spawn worker threads
        num_threads = min(self.max_threads, len(endpoints))
        threads = []
        for i in range(num_threads):
            t = Thread(target=self.worker)
            threads.append(t)
            t.start()

        # wait for the threads to complete
        for t in threads:
            t.join()

        # parse results queue
        results_by_name = {}
        while not self.results.empty():
            name, code, message = self.results.get()
            results_by_name[name] = (code, message)

        # find most critical status, deterministically
        # based on the order of endpoints
        status = EXIT_OK
        info = ''
        tags = ''
        for endpoint in endpoints:
            name = endpoint['name']
            code, message = results_by_name[name]
            if code != 200:
                level = LEVELS[endpoint['level']]
                if level[0] > status[0]:
                    status = level
                    info = name + ': ' + message
                    if 'tags' in endpoint:
                        tags = endpoint['tags']
                    else:
                        tags = ''

        self.halt(status, info, tags)

    def worker(self):
        while True:
            # get the next endpoint
            try:
                endpoint = self.endpoints.get_nowait()
            except Queue.Empty:
                return

            url = endpoint['url']
            name = endpoint['name']
            timeout = self.timeout
            if 'timeout' in endpoint:
                timeout = endpoint['timeout']

            # request the endpoint URL
            try:
                req = urllib2.Request(url=url)
                f = urllib2.urlopen(req, timeout=timeout)
                f.read()
                code = 200
                message = 'OK'
            except urllib2.HTTPError, e:
                code = e.code
                message = e.read()
            except urllib2.URLError, e:
                code = 500
                message = 'URL Error ' + e.reason
            except socket.timeout:
                code = 500
                message = 'Timeout'
            except Exception:
                code = 500
                message = 'HTTP Exception'

            # save the results and complete the task
            self.results.put((name, code, message))
            self.endpoints.task_done()

    def halt(self, level, info='', tags=''):
        code, message = level
        if code == EXIT_OK[0]:
            output = ' '.join([EXIT_OK[1], self.metadata_url])
        else:
            contact = self.tag
            if tags:
                contact += ',' + tags
            output = ' '.join([message, 'Contact:', contact, 'Level:', message, info])
        print output[:self.max_output_len]
        sys.exit(code)

    def halt_config_error(self, info):
        msg = CONFIG_ERROR
        if info:
            msg += ': ' + info
        self.tag = self.default_contact
        self.halt(self.default_level, msg)


def main():
    parser = argparse.ArgumentParser(description='Runs application monitoring tests')
    parser.add_argument('metadata_url', metavar='URL', help='location of endpoint metadata')
    parser.add_argument('--contact', help='default contact for the test')
    parser.add_argument('--level', help='default level for the test', choices=LEVELS.keys())
    parser.add_argument('--timeout', help='network request timeout, in seconds (default %s)' % DEFAULT_TIMEOUT, default=DEFAULT_TIMEOUT)
    parser.add_argument('--threads', help='maximum number of threads to use (default %s)' % MAX_THREADS, default=MAX_THREADS)
    parser.add_argument('--length', help='maximum output length (default %s)' % MAX_OUTPUT_LEN, default=MAX_OUTPUT_LEN)
    args = parser.parse_args()
    harness = TestHarness(args.metadata_url, args.contact, LEVELS[args.level], args.threads, args.timeout, args.length)
    harness.run()

if __name__ == '__main__':
    main()
