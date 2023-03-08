
import inspect
import os
from shutil import rmtree
from argparse import Namespace
from subprocess import Popen, PIPE
from typing import List

import pytest
from prometheus_client import CollectorRegistry, write_to_textfile

# Import the exporter itself
from ethtool_exporter import EthtoolCollector


class TestEthtoolCollector:

    default_nic_types = [
        # Intel
        "i40e28_sfp_10gsr85", "i40e21_int_tp", "ixgbe418_sfp_10gsr85", "igb56_int_tp",
        # Broadcom
        "bnxten418_sfp_10gwtf1", "bnxten_418_sfp_10gsr85",
        # Realtek
        "tg3_418_int_tp"
    ]


    default_args_dict = {
        "debug": False,
        "quiet": False,
        "interface_regex": ".*",
        "whitelist_regex": None,
        "blacklist_regex": None,
        "collect_interface_statistics": True,
        "collect_interface_info": True,
        "collect_sfp_diagnostics": True,
        "summarize_queues": True
    }

    def prepare_pseudo_sys_class_net_dir(self):
        os.mkdir(".tests/sys_class_net")
        for nic_type in self.default_nic_types:
            os.symlink("/dev/null", f".tests/sys_class_net/{nic_type}")

    @classmethod
    def setup_class(cls):
        os.mkdir(".tests")
        cls.prepare_pseudo_sys_class_net_dir(cls)

    @classmethod
    def teardown_class(cls):
        rmtree(".tests")

    def check_exporter(self, current_func_name, custom_args_dict={}, nic_type=None):
        collector_args_dict = {**self.default_args_dict, **custom_args_dict}
        collector_args = Namespace(**collector_args_dict)

        ethtool_collector = EthtoolCollector(collector_args, "tests/stub_ethtool.sh")
        ethtool_collector.interface_discovery_dir = ".tests/sys_class_net"

        registry = CollectorRegistry()
        registry.register(ethtool_collector)

        if not nic_type:
            nic_type = collector_args.interface_regex
        textfile_name = f".tests/{current_func_name}_{nic_type}_.prom"
        write_to_textfile(textfile_name, registry)

        with Popen(["diff", textfile_name, f"tests/results/{current_func_name}/{nic_type}.prom"], stdout=PIPE, stderr=PIPE) as proc:
            data, err = proc.communicate()
            if proc.returncode != 0:
                err_msg = f"Exporter output doesn't match expected.\nStdout: {data.decode()}\nStderr: {err.decode()}"
                raise Exception(err_msg)

        return ethtool_collector, registry

    # This test can be passed only on linux
    def test_find_physical_interfaces(self):
        ethtool_collector = EthtoolCollector(Namespace(**self.default_args_dict), "tests/stub_ethtool.sh")
        interfaces = list(ethtool_collector.find_physical_interfaces())

    @pytest.mark.parametrize("nic_type", default_nic_types)
    @pytest.mark.parametrize("custom_args", [{}])
    def test_default_settings(self, nic_type, custom_args):
        custom_args = {"interface_regex": nic_type}
        current_func_name = inspect.currentframe().f_code.co_name
        _collector,_registry = self.check_exporter(current_func_name, custom_args, nic_type)

    @pytest.mark.parametrize(
        "custom_args",
        [
            {
                "collect_interface_statistics": False, "collect_interface_info":False, "collect_sfp_diagnostics": True,
                "interface_regex": 'i40e28_sfp_10gsr85'
            }
        ]
    )
    def test_only_sfp_diagnostics(self, custom_args):
        current_func_name = inspect.currentframe().f_code.co_name
        _collector,_registry = self.check_exporter(current_func_name, custom_args)


    @pytest.mark.parametrize(
        "custom_args",
        [
            {
                "collect_interface_statistics": False, "collect_interface_info":True, "collect_sfp_diagnostics": False,
                "interface_regex": 'i40e28_sfp_10gsr85'
            }
        ]
    )
    def test_only_interface_info(self, custom_args):
        current_func_name = inspect.currentframe().f_code.co_name
        _collector,_registry = self.check_exporter(current_func_name, custom_args)


    @pytest.mark.parametrize(
        "custom_args",
        [
            {
                "collect_interface_statistics": True, "collect_interface_info":False, "collect_sfp_diagnostics": False,
                "interface_regex": 'i40e28_sfp_10gsr85'
            }
        ]
    )
    def test_only_interface_statistics(self, custom_args):
        current_func_name = inspect.currentframe().f_code.co_name
        _collector,_registry = self.check_exporter(current_func_name, custom_args)


    @pytest.mark.parametrize(
        "custom_args",
        [
            {
                "collect_interface_statistics": False, "collect_interface_info":False, "collect_sfp_diagnostics": False,
                "interface_regex": 'i40e28_sfp_10gsr85'
            }
        ]
    )
    def test_no_enabled_collectors(self, custom_args):
        current_func_name = inspect.currentframe().f_code.co_name
        _collector,_registry = self.check_exporter(current_func_name, custom_args)


    @pytest.mark.parametrize(
        "custom_args",
        [
            {"summarize_queues": False, "interface_regex": "bnxten418_sfp_10gwtf1"}
        ]
    )
    def test_dont_summarize_queues(self, custom_args):
        current_func_name = inspect.currentframe().f_code.co_name
        _collector,_registry = self.check_exporter(current_func_name, custom_args)


    @pytest.mark.parametrize(
        "custom_args",
        [
            {"blacklist_regex": "^(tx|rx)-[0-9]{1,3}\\.(bytes|packets)$", "interface_regex": "i40e28_sfp_10gsr85"}
        ]
    )
    def test_blacklist_regex(self, custom_args):
        current_func_name = inspect.currentframe().f_code.co_name
        _collector,_registry = self.check_exporter(current_func_name, custom_args)
