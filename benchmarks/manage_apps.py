"""Run the baseline and optimized services against isolated benchmark databases."""
from pathlib import Path
import argparse
import json
import os
import signal
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'benchmarks' / 'results'
APPS = {
    'baseline': (18080, 'onlineorder_baseline', ROOT / 'benchmarks/baseline-source/build/libs/OnlineOrder-0.0.1-SNAPSHOT.jar', 'none'),
    'optimized': (18081, 'onlineorder_optimized', ROOT / 'build/libs/OnlineOrder-0.0.1-SNAPSHOT.jar', 'none'),
    'cached': (18082, 'onlineorder_optimized', ROOT / 'build/libs/OnlineOrder-0.0.1-SNAPSHOT.jar', 'caffeine'),
}

def start(name):
    port, db, jar, cache = APPS[name]
    pidfile = OUT / f'{name}.pid'
    if pidfile.exists():
        raise RuntimeError(f'{name} already has a recorded PID; stop it first')
    args = [
        'java', '-XX:ActiveProcessorCount=2', '-Xms256m', '-Xmx512m', '-jar', str(jar),
        f'--server.address=127.0.0.1', f'--server.port={port}',
        f'--spring.datasource.url=jdbc:postgresql://127.0.0.1:15432/{db}',
        '--spring.datasource.username=postgres', '--spring.datasource.password=benchmark-local-only',
        '--spring.datasource.hikari.maximum-pool-size=20', '--spring.datasource.hikari.minimum-idle=20',
        '--spring.sql.init.mode=never', '--onlineorder.seed-demo=false',
        f'--spring.cache.type={cache}', '--logging.level.root=WARN',
        '--logging.level.org.springframework.jdbc.core=WARN',
        '--logging.level.org.springframework.jdbc.datasource.init=WARN',
        '--logging.level.org.apache.coyote.http11.Http11InputBuffer=WARN',
    ]
    with (OUT / f'{name}.log').open('w') as log:
        process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT, start_new_session=True)
    pidfile.write_text(str(process.pid))
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError((OUT / f'{name}.log').read_text())
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/restaurants/menu', timeout=2) as response:
                if response.status == 200:
                    body = json.load(response)
                    assert len(body) == 100 and len(body[0]['menu_items']) == 100
                    print(f'{name}: ready on {port}, verified 100 restaurants and 100 menus per restaurant', flush=True)
                    return
        except Exception:
            time.sleep(.25)
    raise RuntimeError(f'{name} did not become ready')

def stop(name):
    pidfile = OUT / f'{name}.pid'
    if not pidfile.exists():
        return
    pid = int(pidfile.read_text())
    command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout
    if str(APPS[name][2]) in command:
        os.kill(pid, signal.SIGTERM)
    pidfile.unlink()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['start', 'stop'])
    parser.add_argument('names', nargs='*', default=list(APPS))
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in args.names:
        (start if args.action == 'start' else stop)(name)
