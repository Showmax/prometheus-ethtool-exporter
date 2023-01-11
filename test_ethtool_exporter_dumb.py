
from subprocess import Popen, PIPE
from argparse import Namespace
from prometheus_client import CollectorRegistry, write_to_textfile

# Import ther exporter itself
from ethtool_exporter import EthtoolCollector


def test_default_settings():
    def pathched_find_physical_interfaces() -> list[str]:
        return ["eth0"]

    collector_args = Namespace(debug=False, quiet=False, whitelist_regex=None, blacklist_regex=None)
    ethtool_collector = EthtoolCollector(collector_args, "tests/stub_ethtool.sh")
    ethtool_collector.find_physical_interfaces = pathched_find_physical_interfaces
    registry = CollectorRegistry()
    registry.register(ethtool_collector)

    ethtool_collector.collect()
    write_to_textfile(".test_ethtool_exporter_dumb.prom", registry)

    proc = Popen(["diff", ".test_ethtool_exporter_dumb.prom", "tests/exporter_result.prom"], stdout=PIPE, stderr=PIPE)
    data, err = proc.communicate()
    if proc.returncode != 0:
        err_msg = f"Exporter output doesn't match expected.\nStdout: {data.decode()}\nStdedd: {err.decode()}"
        raise Exception(err_msg)
