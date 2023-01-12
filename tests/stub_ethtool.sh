#! /bin/bash

fixture_name="$(echo $* | sed 's/[ -]/_/g')"
cat "$(dirname $0)/fixtures/$fixture_name"
