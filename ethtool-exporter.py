#!/usr/bin/env python
"""Collect ethtool metrics,publish them via http or save them to a file."""
import argparse
from http.server import HTTPServer
import logging
import os
import re
import socket
import socketserver
import subprocess
import sys
import time

from distutils.spawn import find_executable

import prometheus_client
from prometheus_client.core import GaugeMetricFamily


class EthtoolCollector(object):
    """Collect ethtool metrics,publish them via http or save them to a file."""

    def __init__(self, args=None):
        """Construct the object and parse the arguments."""
        self.args = None
        self.ethtool = None
        if not args:
            args = sys.argv[1:]
        self._parse_args(args)

    def _parse_args(self, args):
        """Parse CLI args and set them to self.args."""
        parser = argparse.ArgumentParser()
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '-f',
            '--textfile-name',
            dest='textfile_name',
            help=('Full file path where to store data for node '
                  'collector to pick up')
        )
        group.add_argument(
            '-l',
            '--listen',
            dest='listen',
            help=('OBSOLETE. Use -L/-p instead. '
                  'Listen host:port, i.e. 0.0.0.0:9417')
        )
        group.add_argument(
            '-p',
            '--port',
            dest='port',
            type=int,
            help='Port to listen on, i.e. 9417'
        )
        parser.add_argument(
            '-L',
            '--listen-address',
            dest='listen_address',
            default='0.0.0.0',
            help='IP address to listen on'
        )
        parser.add_argument(
            '-i',
            '--interval',
            dest='interval',
            type=int,
            help=('Number of seconds between updates of the textfile. '
                  'Default is 5 seconds')
        )
        parser.add_argument(
            '-I',
            '--interface-regex',
            dest='interface_regex',
            default='.*',
            help='Only scrape interfaces whose name matches this regex'
        )
        parser.add_argument(
            '-1',
            '--oneshot',
            dest='oneshot',
            action='store_true',
            default=False,
            help='Run only once and exit. Useful for running in a cronjob'
        )
        parser.add_argument(
            '-q',
            '--quiet',
            dest='quiet',
            action='store_true',
            default=False,
            help='Silence any error messages and warnings'
        )
        wblistgroup = parser.add_mutually_exclusive_group()
        wblistgroup.add_argument(
            '-w',
            '--whitelist-regex',
            dest='whitelist_regex',
            help=('Only include values whose name matches this regex. '
                  '-w and -b are mutually exclusive')
        )
        wblistgroup.add_argument(
            '-b',
            '--blacklist-regex',
            dest='blacklist_regex',
            help=('Exclude values whose name matches this regex. '
                  '-w and -b are mutually exclusive')
        )
        arguments = parser.parse_args(args)
        if arguments.quiet:
            logging.getLogger().setLevel(100)
        if arguments.oneshot and not arguments.textfile_name:
            logging.error('Oneshot has to be used with textfile mode')
            parser.print_help()
            sys.exit(1)
        if arguments.interval and not arguments.textfile_name:
            logging.error('Interval has to be used with textfile mode')
            parser.print_help()
            sys.exit(1)
        if arguments.listen_address and not arguments.port:
            logging.error('Listen address has to be used with a listen port')
            parser.print_help()
            sys.exit(1)
        if not arguments.interval:
            arguments.interval = 5
        self.args = vars(arguments)

    def whitelist_blacklist_check(self, stat_name):
        """Check whether stat_name matches whitelist or blacklist."""
        if self.args['whitelist_regex']:
            if re.match(self.args['whitelist_regex'], stat_name):
                return True
            else:
                return False
        if self.args['blacklist_regex']:
            if re.match(self.args['blacklist_regex'], stat_name):
                return False
            else:
                return True
        return True

    def update_ethtool_stats(self, iface, gauge):
        """Update gauge with statistics from ethtool for interface iface."""
        command = [self.ethtool, '-S', iface]
        try:
            proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        except FileNotFoundError:
            logging.critical(self.ethtool + ' not found. Giving up')
            sys.exit(1)
        except PermissionError as e:
            logging.critical('Permission error trying to run '
                             + self.ethtool + ' : {}'.format(e))
            sys.exit(1)
        data, err = proc.communicate()
        if proc.returncode != 0:
            logging.critical('Ethtool returned non-zero return '
                             'code for interface {}, the message'
                             'was: {}'.format(iface, err))
            return
        data = data.decode('utf-8').split('\n')
        key_set = set()
        for line in data:
            # drop empty lines and the header
            if not line or line == 'NIC statistics:':
                continue
            line = line.strip()
            try:
                key, value = line.split(': ')
                key = key.strip()
                value = value.strip()
                value = float(value)
            except ValueError:
                logging.warning('Failed parsing "{}"'.format(line))
                continue
            if not self.whitelist_blacklist_check(key):
                continue
            labels = [iface, key]
            if key not in key_set:
                gauge.add_metric(labels, value)
                key_set.add(key)
            else:
                logging.warning('Item {} already seen, check the source '
                                'data for interface {}'.format(key, iface))

    def collect(self):
        """
        Collect the metrics.

        Collect the metrics and yield them. Prometheus client library
        uses this method to respond to http queries or save them to disk.
        """
        gauge = GaugeMetricFamily(
            'node_net_ethtool', 'Ethtool data', labels=['device', 'type'])
        for iface in self.find_physical_interfaces():
            self.update_ethtool_stats(iface, gauge)
        yield gauge

    def find_physical_interfaces(self):
        """Find physical interfaces and optionally filter them."""
        # https://serverfault.com/a/833577/393474
        root = '/sys/class/net'
        for file in os.listdir(root):
            path = os.path.join(root, file)
            if os.path.islink(path) and 'virtual' not in os.readlink(path):
                if re.match(self.args['interface_regex'], file):
                    yield file


class IPv6HTTPServer(HTTPServer):
    address_family = socket.AF_INET6


if __name__ == '__main__':
    path = os.getenv("PATH", "")
    path = os.pathsep.join([path, "/usr/sbin", "/sbin"])
    ethtool = find_executable("ethtool", path)
    if ethtool is None:
        sys.exit("Error: cannot find ethtool.")

    collector = EthtoolCollector()
    collector.ethtool = ethtool
    registry = prometheus_client.CollectorRegistry()
    registry.register(collector)
    EthtoolMetricsHandler = prometheus_client.MetricsHandler.factory(registry)
    args = collector.args
    if args['listen'] or args['port']:
        if args['listen']:
            logging.warning('You are using obsolete argument -l.'
                            'Please switch to -L and -p')
            ip, port = args['listen'].rsplit(':', 1)
        else:
            ip = args['listen_address']
            port = args['port']
        # Remove optional IPv6 braces if present, i.e. [::1] => ::1
        ip = ip.replace('[', '').replace(']', '')
        port = int(port)
        if ':' in ip:
            server_class = IPv6HTTPServer
        else:
            server_class = HTTPServer
        httpd = server_class((ip, port), EthtoolMetricsHandler)
        httpd.serve_forever()
        while True:
            time.sleep(3600)
    if args['textfile_name']:
        while True:
            collector.collect()
            prometheus_client.write_to_textfile(args['textfile_name'],
                                                registry)
            if collector.args['oneshot']:
                sys.exit(0)
            time.sleep(args['interval'])
