# prometheus-ethtool-exporter
A python script that pulls information from ethtool and publishes it in prometheus format.

This utility drew some inspiration from https://github.com/adeverteuil/ethtool_exporter, but simplified it
and added a few new features. This version has consistent label names with node_exporter, which makes
it more intuitive to use. You're also able to make this script export the data in prometheus file
format on disk to achieve easier integration with node exporter without the need to run another
daemon.

You can either use this as a standalone exporter that listens on an HTTP port, or use it to save data
on disk in a .prom file either periodically or just once, and run it from cron or something similar.

# Usage
```
usage: ethtool-exporter.py [-h] (-f TEXTFILE_NAME | -l LISTEN) [-i INTERVAL]
                           [-I INTERFACE_REGEX] [-1]
                           [-w WHITELIST_REGEX | -b BLACKLIST_REGEX]

optional arguments:
  -h, --help            show this help message and exit
  -f TEXTFILE_NAME, --textfile-name TEXTFILE_NAME
                        Full file path where to store data for node collector
                        to pick up
  -l LISTEN, --listen LISTEN
                        Listen host:port, i.e. 0.0.0.0:9417
  -i INTERVAL, --interval INTERVAL
                        Number of seconds between updates of the textfile.
                        Default is 5 seconds
  -I INTERFACE_REGEX, --interface-regex INTERFACE_REGEX
                        Only scrape interfaces whose name matches this regex
  -1, --oneshot         Run only once and exit. Useful for running in a
                        cronjob
  -w WHITELIST_REGEX, --whitelist-regex WHITELIST_REGEX
                        Only include values whose name matches this regex. -w
                        and -b are mutually exclusive
  -b BLACKLIST_REGEX, --blacklist-regex BLACKLIST_REGEX
                        Exclude values whose name matches this regex. -w and
                        -b are mutually exclusive
```

# Blog
Blogpost describing how we debugged a production issue with the help of this
exporter is [published on our blog](https://shw.mx/ethtool).
