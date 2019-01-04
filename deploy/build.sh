#!/bin/sh

set -eu -o pipefail

mkdir -p tmp

curl https://raw.githubusercontent.com/Showmax/prometheus-ethtool-exporter/master/ethtool-exporter.py \
     -o tmp/ethtool-exporter.py

python -m pip download --no-binary :all: -r requirements.txt --require-hashes -d tmp

docker build -t ethtool-exporter .
