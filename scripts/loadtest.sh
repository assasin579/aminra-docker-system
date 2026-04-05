#!/bin/bash
# Quick load test — 10 users, ramp 2/s, 60 seconds
pip install -q locust 2>/dev/null
locust -f tests/loadtest/locustfile.py \
    --host=${TEST_BACKEND_URL:-http://localhost:8100} \
    --headless -u ${USERS:-10} -r ${RAMP:-2} -t ${DURATION:-60s} \
    --csv=tests/loadtest/results
