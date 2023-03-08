
import inspect
import os
from shutil import rmtree
from argparse import Namespace
from subprocess import Popen, PIPE
from typing import List

import pytest
from prometheus_client import CollectorRegistry, write_to_textfile

def _get_curr_time():
    return int(1678287354)

# Import the exporter itself
from ethtool_exporter import EthtoolCollector
EthtoolCollector._get_curr_time = _get_curr_time


class TestEthtoolCollector:

    default_nic_types = [
        # Intel
        "i40e28_sfp_10gsr85", "i40e21_int_tp", "ixgbe418_sfp_10gsr85", "igb56_int_tp", "i40e21_int_broken",
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
        "summarize_queues": True,
        "textfile_name": "/dev/null"
    }

    def prepare_pseudo_sys_class_net_dir(self):
        os.mkdir(".tests/sys_class_net")
        for nic_type in self.default_nic_types:
            os.symlink("/dev/null", f".tests/sys_class_net/{nic_type}")
        os.symlink("/dev/null", f".tests/sys_class_net/i40e28_sfp_non_existent")

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

    def test_find_physical_interfaces(self):
        # This test can be passed only on linux
        if os.sys.platform == 'linux':
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

    @pytest.mark.parametrize(
        "custom_args",
        [
            {
                "interface_regex": 'i40e28_sfp_10gsr85'
            }
        ]
    )
    def test_absent_ethtool(self, custom_args):
        current_func_name = inspect.currentframe().f_code.co_name
        collector_args_dict = {**self.default_args_dict, **custom_args}
        collector_args = Namespace(**collector_args_dict)

        with pytest.raises(SystemExit) as pytest_wrapped_e:
            ethtool_collector = EthtoolCollector(collector_args, "/whatever/stub_ethtool.sh")
            ethtool_collector.interface_discovery_dir = ".tests/sys_class_net"
            registry = CollectorRegistry()
            registry.register(ethtool_collector)
            nic_type = collector_args.interface_regex
            textfile_name = f".tests/{current_func_name}_{nic_type}_.prom"
            write_to_textfile(textfile_name, registry)
        assert pytest_wrapped_e.type == SystemExit
        assert pytest_wrapped_e.value.code == 1

    @pytest.mark.parametrize(
        "custom_args",
        [
            {
                "interface_regex": 'i40e28_sfp_10gsr85'
            }
        ]
    )
    def test_unexeceable_ethtool(self, custom_args):
        current_func_name = inspect.currentframe().f_code.co_name
        collector_args_dict = {**self.default_args_dict, **custom_args}
        collector_args = Namespace(**collector_args_dict)

        with pytest.raises(SystemExit) as pytest_wrapped_e:
            ethtool_collector = EthtoolCollector(collector_args, ".tests/sys_class_net")
            ethtool_collector.interface_discovery_dir = ".tests/sys_class_net"
            registry = CollectorRegistry()
            registry.register(ethtool_collector)
            nic_type = collector_args.interface_regex
            textfile_name = f".tests/{current_func_name}_{nic_type}_.prom"
            write_to_textfile(textfile_name, registry)
        assert pytest_wrapped_e.value.code == 1

    @pytest.mark.parametrize(
        "custom_args",
        [
            {
                "interface_regex": 'i40e28_sfp_non_existent'
            }
        ]
    )
    def test_broken_ethtool(self, custom_args):
        current_func_name = inspect.currentframe().f_code.co_name
        collector_args_dict = {**self.default_args_dict, **custom_args}
        collector_args = Namespace(**collector_args_dict)

        with pytest.raises(UnicodeDecodeError):
            ethtool_collector = EthtoolCollector(collector_args, "xz")
            ethtool_collector.interface_discovery_dir = ".tests/sys_class_net"
            registry = CollectorRegistry()
            registry.register(ethtool_collector)
            nic_type = collector_args.interface_regex
            textfile_name = f".tests/{current_func_name}_{nic_type}_.prom"
            write_to_textfile(textfile_name, registry)

    def test_unfindable_ethtool(self):
        from ethtool_exporter import _get_ethtool_path
        with pytest.raises(SystemExit):
            _get_ethtool_path()

    def test_main(self):
        from ethtool_exporter import main
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            main()
        assert pytest_wrapped_e.value.code == 2
