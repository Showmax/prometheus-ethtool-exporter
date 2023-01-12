#! /bin/bash

case "$*" in
  '-S eth0')
    cat "$(dirname $0)/fixture_s_eth0"
    ;;

  '-m eth0')
    cat "$(dirname $0)/fixture_m_eth0"
    ;;

  'eth0')
    cat "$(dirname $0)/fixture_eth0"
    ;;

  *)
    echo "Wrong params <$*>"
    exit 1
    ;;
esac
