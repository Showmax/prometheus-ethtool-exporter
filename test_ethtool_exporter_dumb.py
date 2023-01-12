
import pytest
from subprocess import Popen, PIPE
from argparse import Namespace
from prometheus_client import CollectorRegistry, write_to_textfile
from typing import List

# Import ther exporter itself
from ethtool_exporter import EthtoolCollector

nic_type_list = ["ixgbe418_sfp_10gsr85", "i40e21_int_tp"]

@pytest.mark.parametrize("nic_type", nic_type_list)
def test_default_settings(nic_type):
    def pathched_find_physical_interfaces() -> List[str]:
        return [nic_type]

    collector_args = Namespace(debug=False, quiet=False, whitelist_regex=None, blacklist_regex=None)
    ethtool_collector = EthtoolCollector(collector_args, "tests/stub_ethtool.sh")
    ethtool_collector.find_physical_interfaces = pathched_find_physical_interfaces
    registry = CollectorRegistry()
    registry.register(ethtool_collector)

    ethtool_collector.collect()
    write_to_textfile(f".test_{nic_type}.prom", registry)

    proc = Popen(["diff", f".test_{nic_type}.prom", f"tests/result_{nic_type}.prom"], stdout=PIPE, stderr=PIPE)
    data, err = proc.communicate()
    if proc.returncode != 0:
        err_msg = f"Exporter output doesn't match expected.\nStdout: {data.decode()}\nStderr: {err.decode()}"
        raise Exception(err_msg)
