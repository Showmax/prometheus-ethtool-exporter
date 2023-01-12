# prometheus-ethtool-exporter
A python script that pulls information from ethtool and publishes it in prometheus format.

This utility drew some inspiration from https://github.com/adeverteuil/ethtool_exporter, but simplified it
and added a few new features. This version has consistent label names with node_exporter, which makes
it more intuitive to use. You're also able to make this script export the data in prometheus file
format on disk to achieve easier integration with node exporter without the need to run another
daemon.

You can either use this as a standalone exporter that listens on an HTTP port, or use it to save data
on disk in a .prom file either periodically or just once, and run it from cron or something similar.

**_WARNING_**: Since version 0.6.0 Python 3.6 - 3.8 is supported again.  
**_WARNING_**: Since version 0.5.0 Python 3.9+ is required.  
**_WARNING_**: Since version 0.3.0 Python 3.0+ is required. If you need to use Python2, use the 0.2.6 version.

# Usage
```
usage: ethtool_exporter.py [-h] (-f TEXTFILE_NAME | -l LISTEN | -p PORT) [-L LISTEN_ADDRESS] [-i INTERVAL] [-I INTERFACE_REGEX] [-1] [--debug] [-q]
                           [-w WHITELIST_REGEX | -b BLACKLIST_REGEX]

optional arguments:
  -h, --help            show this help message and exit
  -f TEXTFILE_NAME, --textfile-name TEXTFILE_NAME
                        Full file path where to store data for node collector to pick up
  -l LISTEN, --listen LISTEN
                        OBSOLETE. Use -L/-p instead. Listen host:port, i.e. 0.0.0.0:9417
  -p PORT, --port PORT  Port to listen on, i.e. 9417
  -L LISTEN_ADDRESS, --listen-address LISTEN_ADDRESS
                        IP address to listen on
  -i INTERVAL, --interval INTERVAL
                        Number of seconds between updates of the textfile. Default is 5 seconds
  -I INTERFACE_REGEX, --interface-regex INTERFACE_REGEX
                        Only scrape interfaces whose name matches this regex
  -1, --oneshot         Run only once and exit. Useful for running in a cronjob
  --debug               Set logging level to DEBUG and see more.
  -q, --quiet           Silence any error messages and warnings
  -w WHITELIST_REGEX, --whitelist-regex WHITELIST_REGEX
                        Only include values whose name matches this regex. -w and -b are mutually exclusive
  -b BLACKLIST_REGEX, --blacklist-regex BLACKLIST_REGEX
                        Exclude values whose name matches this regex. -w and -b are mutually exclusive
```

# Blog
Blogpost describing how we debugged a production issue with the help of this
exporter is [published on our blog](https://shw.mx/ethtool).
