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
from prometheus_client.core import GaugeMetricFamily, InfoMetricFamily


class EthtoolCollector(object):
    """Collect ethtool metrics,publish them via http or save them to a file."""

    def __init__(self, args=None):
        """Construct the object and parse the arguments."""
        self.args = None
        self.ethtool = None
        self.basic_info_whitelist = [
                'speed',
                'duplex',
                'port',
                'link_detected',
                ]
        self.xcvr_info_whitelist = [
                'identifier',
                'extended_identifier',
                'connector',
                'transceiver_type',
                'length_smf_km',
                'length_smf',
                'length_50um',
                'length_62_5um',
                'length_copper',
                'length_om3',
                'laser_wavelength',
                'vendor_name',
                'vendor_oui',
                'vendor_pn',
                'vendor_rev',
                'vendor_sn',
                'laser_bias_current_high_alarm_threshold',
                'laser_bias_current_low_alarm_threshold',
                'laser_bias_current_high_warning_threshold',
                'laser_bias_current_low_warning_threshold',
                'laser_output_power_high_alarm_threshold',
                'laser_output_power_low_alarm_threshold',
                'laser_output_power_high_warning_threshold',
                'laser_output_power_low_warning_threshold',
                'module_temperature_high_alarm_threshold',
                'module_temperature_low_alarm_threshold',
                'module_temperature_high_warning_threshold',
                'module_temperature_low_warning_threshold',
                'module_voltage_high_alarm_threshold',
                'module_voltage_low_alarm_threshold',
                'module_voltage_high_warning_threshold',
                'module_voltage_low_warning_threshold',
                'laser_rx_power_high_alarm_threshold',
                'laser_rx_power_low_alarm_threshold',
                'laser_rx_power_high_warning_threshold',
                'laser_rx_power_low_warning_threshold',
                ]
        self.xcvr_sensors_whitelist = [
                'laser_bias_current',
                'laser_output_power',
                'receiver_signal_average_optical_power',
                'module_temperature',
                'module_voltage',
                ]
        self.xcvr_alarms_base = [
                'laser_bias_current',
                'laser_output_power',
                'module_temperature',
                'module_voltage',
                'laser_rx_power',
                ]
        self.xcvr_alamrs_ext = [
                '_high_alarm',
                '_low_alarm',
                '_high_warning',
                '_low_warning',
                ]
        # Cartesian product of the two lists above
        self.xcvr_alarms_whitelist = [i+j for i in self.xcvr_alarms_base for j in self.xcvr_alamrs_ext]

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
        if arguments.listen_address and not arguments.port and not arguments.textfile_name:
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

    def run_ethtool(self, iface, parameter, quiet=False):
        """Run ethtool with select parameter"""
        if parameter:
            command = [self.ethtool, parameter, iface]
        else:
            command = [self.ethtool, iface]
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
            if not quiet:
                logging.critical('Ethtool returned non-zero return '
                                 'code for interface {}, the message'
                                 'was: {}'.format(iface, err))
            return False
        return data

    def update_ethtool_stats(self, iface, gauge):
        """Update gauge with statistics from ethtool for interface iface."""
        data = self.run_ethtool(iface, '-S')
        if not data:
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

    def update_basic_info(self, iface, info):
        """Update metric with info from ethtool for interface iface."""
        data = self.run_ethtool(iface, '')
        if not data:
            return
        data = data.decode('utf-8').split('\n')
        labels = {'device': iface}
        for line in data:
            # drop empty lines and the header
            if not line or line.startswith('Settings for '):
                continue
            # drop lines without : - continuation of previous line
            if ':' not in line:
                continue
            line = line.strip()
            linesplit = line.split(': ')
            if len(linesplit) < 2:
                print(linesplit)
            key, value = line.split(': ')
            key = key.strip().replace(' ', '_').lower()
            if key not in self.basic_info_whitelist:
                continue
            # special handling for special values
            try:
                if key == 'speed':
                    if value.endswith('Kb/s'):
                        val = float(value.split('Mb/s')[0]) * 1000
                    elif value.endswith('Mb/s'):
                        val = float(value.split('Mb/s')[0]) * 1000000
                    elif value.endswith('Gb/s'):
                        val = float(value.split('Mb/s')[0]) * 1000000000
                    elif value == 'Unknown!':
                        val = 0
                    else:
                        val = float(value)
                    value = str(val)
            except ValueError:
                logging.warning('Failed parsing "{}"'.format(line))
                continue
            labels[key] = value
        info.add_metric(labels.values(), labels)

    def add_split(self, sensors, iface, key, value):
        """Helper method to split values like '10.094 mA'"""
        val, unit = value.split(' ', 1)
        unit = unit.replace(' ', '_')
        unit = unit.replace('.', '_')
        unit = unit.replace(',', '_')
        labels = [iface, key + '_' + unit]
        sensors.add_metric(labels=labels, value=float(val))

    def update_xcvr_info(self, iface, info, sensors, alarms):
        """Update transceiver metrics with info from ethtool."""
        data = self.run_ethtool(iface, '-m', quiet=True)
        if not data:
            # This usually happens when transceiver is missing
            logging.info('Cannot get transceiver data for ' + iface)
            return
        data = data.decode('utf-8').split('\n')
        info_labels = {'device': iface}
        for line in data:
            # drop empty lines and the header
            if not line or line.startswith('Settings for '):
                continue
            # drop lines without : - continuation of previous line
            if ':' not in line:
                continue
            line = line.strip()
            key, value = line.split(': ', 1)
            key = key.strip().replace(' ', '_').replace('(', '').replace(')', '').lower()
            value = value.strip()
            if key in self.xcvr_info_whitelist:
                info_labels[key] = value
            elif key in self.xcvr_sensors_whitelist:
                if key == 'laser_bias_current' or key == 'module_voltage':
                    self.add_split(sensors, iface, key, value)
                elif key == 'laser_output_power' or key == 'receiver_signal_average_optical_power' or key == 'module_temperature':
                    for val in value.split(' / '):
                        self.add_split(sensors, iface, key, val)
            elif key in self.xcvr_alarms_whitelist:
                if value == 'Off':
                    continue
                labels = {
                        'device': iface,
                        'type': key,
                        'value': value,
                        }
                alarms.add_metric(labels=labels, value=1.0)
        info.add_metric(info_labels.values(), info_labels)

    def collect(self):
        """
        Collect the metrics.

        Collect the metrics and yield them. Prometheus client library
        uses this method to respond to http queries or save them to disk.
        """
        gauge = GaugeMetricFamily(
            'node_net_ethtool', 'Ethtool data', labels=['device', 'type'])
        basic_info = InfoMetricFamily(
            'node_net_ethtool', 'Ethtool device information',
            labels=['device'])
        xcvr_info = InfoMetricFamily(
            'node_net_ethtool_xcvr', 'Ethtool device transceiver information',
            labels=['device'])
        sensors = GaugeMetricFamily(
            'node_net_ethtool_xcvr_sensors', 'Ethtool transceiver sensors', labels=['device', 'type'])
        alarms = GaugeMetricFamily(
            'node_net_ethtool_xcvr_alarms', 'Ethtool transceiver sensor alarms', labels=['device', 'type'])
        for iface in self.find_physical_interfaces():
            self.update_ethtool_stats(iface, gauge)
            self.update_basic_info(iface, basic_info)
            self.update_xcvr_info(iface, xcvr_info, sensors, alarms)
        yield basic_info
        yield xcvr_info
        yield sensors
        yield alarms
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
