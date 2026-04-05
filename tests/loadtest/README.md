# AMINRA Load Testing

Load tests for the AMINRA backend using [Locust](https://locust.io/).

## Install

```bash
pip install -r tests/loadtest/requirements.txt
```

## Run

### With Web UI

```bash
locust -f tests/loadtest/locustfile.py --host=http://localhost:8100
```

Open http://localhost:8089 to configure and start the test.

### Headless

```bash
locust -f tests/loadtest/locustfile.py --host=http://localhost:8100 --headless -u 10 -r 2 -t 60s
```

### Quick wrapper script

```bash
./scripts/loadtest.sh
```

Override defaults with environment variables:

```bash
USERS=50 RAMP=5 DURATION=120s ./scripts/loadtest.sh
```
