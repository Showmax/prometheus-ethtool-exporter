#!/usr/bin/env python3
"""Collect ethtool metrics,publish them via http or save them to a file."""
import re
from argparse import ArgumentParser, Namespace
from distutils.spawn import find_executable
from logging import CRITICAL, DEBUG, INFO, Logger, basicConfig, getLogger
from os import environ
from pathlib import Path
from subprocess import PIPE, Popen
from sys import argv, exit
from time import sleep
from typing import Iterator, Optional, Union

from prometheus_client import CollectorRegistry, start_http_server, write_to_textfile
from prometheus_client.core import GaugeMetricFamily, InfoMetricFamily


class EthtoolCollector:
    """Collect ethtool metrics,publish them via http or save them to a file."""

    def __init__(self, args: Optional[list[str]] = None):
        """Construct the object and parse the arguments."""
        self.basic_info_whitelist = (
            "speed",
            "duplex",
            "port",
            "link_detected",
        )
        self.xcvr_info_whitelist = (
            "identifier",
            "extended_identifier",
            "connector",
            "transceiver_type",
            "length_smf_km",
            "length_smf",
            "length_50um",
            "length_62_5um",
            "length_copper",
            "length_om3",
            "laser_wavelength",
            "vendor_name",
            "vendor_oui",
            "vendor_pn",
            "vendor_rev",
            "vendor_sn",
            "laser_bias_current_high_alarm_threshold",
            "laser_bias_current_low_alarm_threshold",
            "laser_bias_current_high_warning_threshold",
            "laser_bias_current_low_warning_threshold",
            "laser_output_power_high_alarm_threshold",
            "laser_output_power_low_alarm_threshold",
            "laser_output_power_high_warning_threshold",
            "laser_output_power_low_warning_threshold",
            "module_temperature_high_alarm_threshold",
            "module_temperature_low_alarm_threshold",
            "module_temperature_high_warning_threshold",
            "module_temperature_low_warning_threshold",
            "module_voltage_high_alarm_threshold",
            "module_voltage_low_alarm_threshold",
            "module_voltage_high_warning_threshold",
            "module_voltage_low_warning_threshold",
            "laser_rx_power_high_alarm_threshold",
            "laser_rx_power_low_alarm_threshold",
            "laser_rx_power_high_warning_threshold",
            "laser_rx_power_low_warning_threshold",
        )
        self.xcvr_sensors_whitelist = (
            "laser_bias_current",
            "laser_output_power",
            "receiver_signal_average_optical_power",
            "module_temperature",
            "module_voltage",
        )
        self.xcvr_alarms_base = (
            "laser_bias_current",
            "laser_output_power",
            "module_temperature",
            "module_voltage",
            "laser_rx_power",
        )
        self.xcvr_alarms_ext = (
            "_high_alarm",
            "_low_alarm",
            "_high_warning",
            "_low_warning",
        )
        # Cartesian product of the two lists above
        self.xcvr_alarms_whitelist = [
            f"{base}{alarm}"
            for base in self.xcvr_alarms_base
            for alarm in self.xcvr_alarms_ext
        ]
        self.ethtool: str = ""
        self.args: Namespace = self._parse_arguments(args or argv[1:])
        self.logger: Logger = self._setup_logger()

    def _setup_logger(self) -> Logger:
        """Setup a logger for exporter.

        :return: Logger instance.
        """
        log_level = DEBUG if self.args.debug else INFO
        if self.args.quiet:
            log_level = CRITICAL

        basicConfig(level=log_level)
        return getLogger("ethtool-collector")

    def _parse_arguments(self, arguments: list[str]) -> Namespace:
        """Parse CLI args.

        :param arguments: Args from override or CLI to be parsed into Namespace.
        :return: Parsed args.
        """
        parser = ArgumentParser()
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            "-f",
            "--textfile-name",
            help="Full file path where to store data for node collector to pick up",
        )
        group.add_argument(
            "-l",
            "--listen",
            help="OBSOLETE. Use -L/-p instead. Listen host:port, i.e. 0.0.0.0:9417",
        )
        group.add_argument(
            "-p", "--port", type=int, help="Port to listen on, i.e. 9417"
        )
        parser.add_argument(
            "-L", "--listen-address", default="0.0.0.0", help="IP address to listen on"
        )
        parser.add_argument(
            "-i",
            "--interval",
            type=int,
            help=(
                "Number of seconds between updates of the textfile. "
                "Default is 5 seconds"
            ),
        )
        parser.add_argument(
            "-I",
            "--interface-regex",
            default=".*",
            help="Only scrape interfaces whose name matches this regex",
        )
        parser.add_argument(
            "-1",
            "--oneshot",
            action="store_true",
            default=False,
            help="Run only once and exit. Useful for running in a cronjob",
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            default=False,
            help="Set logging level to DEBUG and see more.",
        )
        parser.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            default=False,
            help="Silence any error messages and warnings",
        )
        wb_list_group = parser.add_mutually_exclusive_group()
        wb_list_group.add_argument(
            "-w",
            "--whitelist-regex",
            help=(
                "Only include values whose name matches this regex. "
                "-w and -b are mutually exclusive"
            ),
        )
        wb_list_group.add_argument(
            "-b",
            "--blacklist-regex",
            help=(
                "Exclude values whose name matches this regex. "
                "-w and -b are mutually exclusive"
            ),
        )
        parsed_arguments = parser.parse_args(arguments)
        self._check_parsed_arguments(parser, parsed_arguments)
        # Set default value if none is set after validation.
        if not parsed_arguments.interval:
            parsed_arguments.interval = 5
        return parsed_arguments

    def _check_parsed_arguments(
        self, parser: ArgumentParser, parsed_arguments: Namespace
    ):
        """CHeck if arguments have the required / allowed combinations of values.

        :param parser: Used argument parser.
        :param parsed_arguments: Parsed arguments using the argument parser.
        """
        if parsed_arguments.oneshot and not parsed_arguments.textfile_name:
            self.logger.error("Oneshot has to be used with textfile mode")
            parser.print_help()
            exit(1)
        if parsed_arguments.interval and not parsed_arguments.textfile_name:
            self.logger.error("Interval has to be used with textfile mode")
            parser.print_help()
            exit(1)
        if (
            parsed_arguments.listen_address
            and not parsed_arguments.port
            and not parsed_arguments.textfile_name
        ):
            self.logger.error("Listen address has to be used with a listen port")
            parser.print_help()
            exit(1)

    def whitelist_blacklist_check(self, stat_name: str) -> bool:
        """Check whether stat_name matches whitelist or blacklist.

        :param stat_name: Name of the statistic to be checked against lists.
        :return: Bool if statistic is allowed.
        """
        if self.args.whitelist_regex:
            return re.match(self.args.whitelist_regex, stat_name) is not None
        if self.args.blacklist_regex:
            return re.match(self.args.blacklist_regex, stat_name) is None
        return True

    def run_ethtool(self, interface: str, parameter: str) -> Optional[bytes]:
        """Run ethtool with select parameter.

        :param interface: Interface we want to make metrics from.
        :param parameter: Additional params for running ethtool command.
        """
        command = [self.ethtool, interface]
        if parameter:
            command = [self.ethtool, parameter, interface]
        try:
            self.logger.debug(f"ethtool command: {command}")
            proc = Popen(command, stdout=PIPE, stderr=PIPE)
        except FileNotFoundError:
            self.logger.critical(f"{self.ethtool} not found. Giving up")
            exit(1)
        except PermissionError as e:
            self.logger.critical(f"Permission error trying to run {self.ethtool}: {e}")
            exit(1)
        data, err = proc.communicate()
        if proc.returncode != 0:
            self.logger.error(
                "Ethtool returned non-zero return "
                f"code for interface {interface}, the message "
                f"was: {err}"
            )
            return None
        return data

    def update_ethtool_stats(self, interface: str, gauge: GaugeMetricFamily):
        """Update gauge with statistics from ethtool for interface.

        :param interface: Interface we make metrics from.
        :param gauge: Destination metric to put the data in.
        """
        if not (data := self.run_ethtool(interface, "-S")):
            return
        key_set = set()
        for line in data.decode("utf-8").splitlines():
            line = line.strip()
            # drop empty lines and the header
            if not line or line == "NIC statistics:":
                continue
            try:
                if not (key_val := self._parse_key_value_line(line)):
                    continue

                key, value = key_val
                key = key.strip()
                value = float(value.strip())
            except ValueError:
                self.logger.warning(f'Failed parsing "{line}"')
                continue

            if not self.whitelist_blacklist_check(key):
                continue

            if key not in key_set:
                gauge.add_metric([interface, key], value)
                key_set.add(key)

            else:
                self.logger.warning(
                    f"Item {key} already seen, check the source data for "
                    f"interface {interface}"
                )

    def update_basic_info(self, interface: str, info: InfoMetricFamily):
        """Update metric with info from ethtool for interface interface.

        :param interface: Interface we make metrics from.
        :param info: Destination metric to put the data in.
        """
        if not (data := self.run_ethtool(interface, "")):
            return

        labels = {"device": interface}
        for line in data.decode("utf-8").splitlines():
            line = line.strip()
            # drop empty lines
            # drop line with the header
            # drop lines without : - continuation of previous line
            if not line or line.startswith("Settings for ") or ":" not in line:
                continue

            if not (key_val := self._parse_key_value_line(line)):
                continue

            key, value = key_val
            key = key.strip().replace(" ", "_").lower()
            if key not in self.basic_info_whitelist:
                continue
            # special handling for special values
            try:
                if key == "speed":
                    value = self._decode_speed_value(value)
            except ValueError:
                self.logger.warning(f'Failed to parse speed in: "{line}"')
                continue
            labels[key] = value
        info.add_metric(labels.values(), labels)

    def _parse_key_value_line(self, line) -> Optional[list[str, str]]:
        """Parse key: value from line if possible.

        :param line: Line to be parsed for key value.
        :return: Parsed key and value from line if parsing was successful.
        """
        if (spliced := line.split(": ", 1)) and len(spliced) == 2:
            return spliced
        self.logger.debug(f"Failed to parse key and value from line: {line}")
        return None

    @staticmethod
    def _decode_speed_value(speed: str) -> str:
        """Convert the speed string with units to a float.

        :param speed: Speed value with unit.
        :return: Only number (float) in string format.
        """
        speed_suffixes = ((1000, "Kb/s"), (1000000, "Mb/s"), (1000000000, "Gb/s"))
        for speed_coefficient, suffix in speed_suffixes:
            if speed.endswith(suffix):
                return str(float(speed.split(suffix)[0]) * speed_coefficient)
        if speed == "Unknown!":
            return "0"
        return speed

    def add_split(
        self,
        sensors: GaugeMetricFamily,
        interface: str,
        metric_name: str,
        metric_value: str,
    ):
        """Helper method to split values like '10.094 mA'

        :param sensors: Destination metric to put the sensors data in.
        :param interface: Interface we make metrics from.
        :param metric_name: Name of the statistic we will parse to metric.
        :param metric_value: Value of the statistic we will parse to metric.
        """
        val, unit = metric_value.split(" ", 1)
        unit = self._remove_separators(unit)
        labels = [interface, f"{metric_name}_{unit}"]
        sensors.add_metric(labels=labels, value=float(val))

    @staticmethod
    def _remove_separators(value: str) -> str:
        """Remove the separators from string.

        :param value: Input string to be processed.
        :return: Processed string without separators.
        """
        return value.strip().replace(",", "_").replace(".", "_").replace(" ", "_")

    def update_xcvr_info(
        self,
        interface: str,
        info: InfoMetricFamily,
        sensors: GaugeMetricFamily,
        alarms: GaugeMetricFamily,
    ):
        """Update transceiver metrics with info from ethtool.

        :param interface: Interface we make metrics from.
        :param info: Destination metric to put the info data in.
        :param sensors: Destination metric to put the sensors data in.
        :param alarms: Destination metric to put the alarms data in.
        """
        if not (data := self.run_ethtool(interface, "-m")):
            # This usually happens when transceiver is missing
            self.logger.info(f"Cannot get transceiver data for {interface}")
            return

        info_labels = {"device": interface}
        for line in data.decode("utf-8").splitlines():
            line = line.strip()
            # drop empty lines
            # drop the header
            # drop lines without : - continuation of previous line
            if not line or line.startswith("Settings for ") or ":" not in line:
                continue

            if not (key_val := self._parse_key_value_line(line)):
                continue

            key, value = key_val
            key = self._remove_separators(key)
            key = key.replace("(", "").replace(")", "").lower()
            value = value.strip()

            if key in self.xcvr_info_whitelist:
                info_labels[key] = value

            elif key in self.xcvr_sensors_whitelist:
                if key in ("module_voltage", "laser_bias_current"):
                    self.add_split(sensors, interface, key, value)

                elif key in (
                    "laser_output_power",
                    "receiver_signal_average_optical_power",
                    "module_temperature",
                ):
                    for val in value.split(" / "):
                        self.add_split(sensors, interface, key, val)

            elif key in self.xcvr_alarms_whitelist:
                if value == "Off":
                    continue
                labels = {
                    "device": interface,
                    "type": key,
                    "value": value,
                }
                alarms.add_metric(labels=labels.values(), value=1.0)
        info.add_metric(info_labels.values(), info_labels)

    def collect(self) -> Iterator[Union[InfoMetricFamily, GaugeMetricFamily]]:
        """
        Collect the metrics.

        Collect the metrics and yield them. Prometheus client library
        uses this method to respond to http queries or save them to disk.
        """
        gauge = GaugeMetricFamily(
            "node_net_ethtool", "Ethtool data", labels=["device", "type"]
        )
        basic_info = InfoMetricFamily(
            "node_net_ethtool", "Ethtool device information", labels=["device"]
        )
        xcvr_info = InfoMetricFamily(
            "node_net_ethtool_xcvr",
            "Ethtool device transceiver information",
            labels=["device"],
        )
        sensors = GaugeMetricFamily(
            "node_net_ethtool_xcvr_sensors",
            "Ethtool transceiver sensors",
            labels=["device", "type"],
        )
        alarms = GaugeMetricFamily(
            "node_net_ethtool_xcvr_alarms",
            "Ethtool transceiver sensor alarms",
            labels=["device", "type"],
        )
        for interface in self.find_physical_interfaces():
            self.update_ethtool_stats(interface, gauge)
            self.update_basic_info(interface, basic_info)
            self.update_xcvr_info(interface, xcvr_info, sensors, alarms)
        yield basic_info
        yield xcvr_info
        yield sensors
        yield alarms
        yield gauge

    def find_physical_interfaces(self) -> list[str]:
        """Find physical interfaces and optionally filter them."""
        # https://serverfault.com/a/833577/393474
        return [
            file.name
            for file in Path("/sys/class/net").iterdir()
            if (
                file.is_symlink()
                and "virtual" not in str(file.readlink().resolve())
                and re.match(self.args.interface_regex, file.name)
            )
        ]


if __name__ == "__main__":
    path = ":".join([environ.get("PATH", ""), "/usr/sbin", "/sbin"])
    # Try to find the executable of ethtool.
    if (ethtool := find_executable("ethtool", path)) is None:
        exit("Error: cannot find ethtool.")
    # Create new instance of EthtoolCollector.
    collector = EthtoolCollector()
    collector.ethtool = ethtool
    collector.logger.debug("Starting ethtool-collector")
    # Create registry for metrics and assign collector.
    registry = CollectorRegistry()
    registry.register(collector)

    # If arguments passed for exposing metrics on port we use them.
    if collector.args.listen or collector.args.port:
        if collector.args.listen:
            collector.logger.warning(
                "You are using obsolete argument -l. Please switch to -L and -p"
            )
            ip, port = collector.args.listen.rsplit(":", 1)
        else:
            ip = collector.args.listen_address
            port = collector.args.port
        # Remove optional IPv6 braces if present, i.e. [::1] => ::1
        ip = ip.replace("[", "").replace("]", "")
        collector.logger.debug(f"Serving metrics on {ip}:{port}")
        # Expose metrics on port and ip.
        start_http_server(port, ip, registry=registry)
        while True:
            sleep(collector.args.interval)

    # If arguments for serving to file are present we use them.
    if collector.args.textfile_name:
        collector.logger.debug(f"Putting metrics into {collector.args.textfile_name}")
        while True:
            collector.collect()
            write_to_textfile(collector.args.textfile_name, registry)
            if collector.args.oneshot:
                exit(0)
            sleep(collector.args.interval)
