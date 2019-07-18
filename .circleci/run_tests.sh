#!/usr/bin/env bash

set -e
set -x

test_report_dir=$1
blockchain_type=$2

# Remove the above arguments, every thing extra will be passed down to coverage
shift 2

mkdir -p ${test_report_dir}

# Using 9min as the dormant timeout, CircleCI will kill the container after
# 10min
# https://support.circleci.com/hc/en-us/articles/360007188574-Build-has-hit-timeout-limit
dormant_timeout=540

# This signal is installed in
# raiden/tests/conftest.py::auto_enable_gevent_monitoring_signal
dormant_signal=SIGUSR1

./tools/kill_if_no_output.py
    --dormant-timeout=${dormant_timeout} \
    --dormant-signal=${dormant_signal} \
    --kill-timeout=15 \
    --kill-signal=SIGKILL \
    coverage \
    run \
    --include="~/raiden/**/*" \
    --parallel-mode \
    --module pytest \
    raiden/tests \
    -vvvvvv \
    --log-config='raiden:DEBUG' \
    --random \
    --junit-xml=${test_report_dir}/results.xml \
    --blockchain-type=${blockchain_type} \
    --select-fail-on-missing \
    --select-from-file selected-tests.txt \
    ${@}