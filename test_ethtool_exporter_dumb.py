
import pytest
from os import path
import inspect
from subprocess import Popen, PIPE
from argparse import Namespace
from prometheus_client import CollectorRegistry, write_to_textfile
from typing import List

# Import ther exporter itself
from ethtool_exporter import EthtoolCollector

nic_type_list = [
    # Intel
    "i40e28_sfp_10gsr85", "i40e21_int_tp", "ixgbe418_sfp_10gsr85", "igb56_int_tp",
    # Broadcom
    "bnxten418_sfp_10gwtf1",
    # Realtek
    "tg3_418_int_tp"
]

@pytest.mark.parametrize("nic_type", nic_type_list)
def test_default_settings(nic_type):
    def pathched_find_physical_interfaces() -> List[str]:
        return [nic_type]

    collector_args = Namespace(
        debug=False, quiet=False,
        whitelist_regex=None, blacklist_regex=None,
        collect_interface_statistics=True, collect_interface_info=True, collect_sfp_diagnostics=True
    )

    ethtool_collector = EthtoolCollector(collector_args, "tests/stub_ethtool.sh")
    ethtool_collector.find_physical_interfaces = pathched_find_physical_interfaces
    registry = CollectorRegistry()
    registry.register(ethtool_collector)

    ethtool_collector.collect()
    textfile = f".{inspect.currentframe().f_code.co_name}_{nic_type}_.prom"
    write_to_textfile(textfile, registry)

    proc = Popen(["diff", textfile, f"tests/results/{inspect.currentframe().f_code.co_name}/{nic_type}.prom"], stdout=PIPE, stderr=PIPE)
    data, err = proc.communicate()
    if proc.returncode != 0:
        err_msg = f"Exporter output doesn't match expected.\nStdout: {data.decode()}\nStderr: {err.decode()}"
        raise Exception(err_msg)

@pytest.mark.parametrize("nic_type", ['i40e28_sfp_10gsr85'])
def test_only_sfp_diagnostics(nic_type):
    def pathched_find_physical_interfaces() -> List[str]:
        return [nic_type]

    collector_args = Namespace(
        debug=False, quiet=False,
        whitelist_regex=None, blacklist_regex=None,
        collect_interface_statistics=False, collect_interface_info=False, collect_sfp_diagnostics=True
    )

    ethtool_collector = EthtoolCollector(collector_args, "tests/stub_ethtool.sh")
    ethtool_collector.find_physical_interfaces = pathched_find_physical_interfaces
    registry = CollectorRegistry()
    registry.register(ethtool_collector)

    ethtool_collector.collect()
    textfile = f".{inspect.currentframe().f_code.co_name}_{nic_type}_.prom"
    write_to_textfile(textfile, registry)

    proc = Popen(["diff", textfile, f"tests/results/{inspect.currentframe().f_code.co_name}/{nic_type}.prom"], stdout=PIPE, stderr=PIPE)
    data, err = proc.communicate()
    if proc.returncode != 0:
        err_msg = f"Exporter output doesn't match expected.\nStdout: {data.decode()}\nStderr: {err.decode()}"
        raise Exception(err_msg)

@pytest.mark.parametrize("nic_type", ['i40e28_sfp_10gsr85'])
def test_only_interface_info(nic_type):
    def pathched_find_physical_interfaces() -> List[str]:
        return [nic_type]

    collector_args = Namespace(
        debug=False, quiet=False,
        whitelist_regex=None, blacklist_regex=None,
        collect_interface_statistics=False, collect_interface_info=True, collect_sfp_diagnostics=False
    )

    ethtool_collector = EthtoolCollector(collector_args, "tests/stub_ethtool.sh")
    ethtool_collector.find_physical_interfaces = pathched_find_physical_interfaces
    registry = CollectorRegistry()
    registry.register(ethtool_collector)

    ethtool_collector.collect()
    textfile = f".{inspect.currentframe().f_code.co_name}_{nic_type}_.prom"
    write_to_textfile(textfile, registry)

    proc = Popen(["diff", textfile, f"tests/results/{inspect.currentframe().f_code.co_name}/{nic_type}.prom"], stdout=PIPE, stderr=PIPE)
    data, err = proc.communicate()
    if proc.returncode != 0:
        err_msg = f"Exporter output doesn't match expected.\nStdout: {data.decode()}\nStderr: {err.decode()}"
        raise Exception(err_msg)

@pytest.mark.parametrize("nic_type", ['i40e28_sfp_10gsr85'])
def test_only_interface_statistics(nic_type):
    def pathched_find_physical_interfaces() -> List[str]:
        return [nic_type]

    collector_args = Namespace(
        debug=False, quiet=False,
        whitelist_regex=None, blacklist_regex=None,
        collect_interface_statistics=True, collect_interface_info=False, collect_sfp_diagnostics=False
    )

    ethtool_collector = EthtoolCollector(collector_args, "tests/stub_ethtool.sh")
    ethtool_collector.find_physical_interfaces = pathched_find_physical_interfaces
    registry = CollectorRegistry()
    registry.register(ethtool_collector)

    ethtool_collector.collect()
    textfile = f".{inspect.currentframe().f_code.co_name}_{nic_type}_.prom"
    write_to_textfile(textfile, registry)

    proc = Popen(["diff", textfile, f"tests/results/{inspect.currentframe().f_code.co_name}/{nic_type}.prom"], stdout=PIPE, stderr=PIPE)
    data, err = proc.communicate()
    if proc.returncode != 0:
        err_msg = f"Exporter output doesn't match expected.\nStdout: {data.decode()}\nStderr: {err.decode()}"
        raise Exception(err_msg)

@pytest.mark.parametrize("nic_type", ['i40e28_sfp_10gsr85'])
def test_no_enabled_collectors(nic_type):
    def pathched_find_physical_interfaces() -> List[str]:
        return [nic_type]

    collector_args = Namespace(
        debug=False, quiet=False,
        whitelist_regex=None, blacklist_regex=None,
        collect_interface_statistics=False, collect_interface_info=False, collect_sfp_diagnostics=False
    )

    ethtool_collector = EthtoolCollector(collector_args, "tests/stub_ethtool.sh")
    ethtool_collector.find_physical_interfaces = pathched_find_physical_interfaces
    registry = CollectorRegistry()
    registry.register(ethtool_collector)

    ethtool_collector.collect()
    textfile = f".{inspect.currentframe().f_code.co_name}_{nic_type}_.prom"
    write_to_textfile(textfile, registry)

    file_size = path.getsize(textfile)
    assert file_size == 0