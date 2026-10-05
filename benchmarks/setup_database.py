"""Create deterministic fixtures inside the dedicated Docker container only."""
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
CONTAINER='onlineorder-resume-benchmark-db'

def sql(db,statement):
    result=subprocess.run(['docker','exec','-i',CONTAINER,'psql','-X','-U','postgres','-d',db,'-At','-v','ON_ERROR_STOP=1'],input=statement,text=True,capture_output=True)
    if result.returncode:raise RuntimeError(result.stderr)
    return result.stdout.strip()

if __name__=='__main__':
    for _ in range(60):
        try:
            sql('postgres','SELECT 1');break
        except RuntimeError:time.sleep(.5)
    else:raise RuntimeError('The dedicated benchmark PostgreSQL container is not ready')
    exists=sql('postgres',"SELECT count(*) FROM pg_database WHERE datname LIKE 'onlineorder_%'")
    if exists!='0':raise RuntimeError('Benchmark databases already exist. Preserve results and recreate only the dedicated temporary container before reseeding.')
    sql('postgres','CREATE EXTENSION IF NOT EXISTS pg_stat_statements; CREATE DATABASE onlineorder_seed;')
    sql('onlineorder_seed',(ROOT/'benchmarks/seed.sql').read_text())
    for name in ['baseline','optimized','index','integration']:
        db='onlineorder_'+name
        sql('postgres',f'CREATE DATABASE {db} TEMPLATE onlineorder_seed;')
        if name!='index':sql(db,(ROOT/'src/main/resources/query-indexes.sql').read_text()+'\nANALYZE;')
        print(db,sql(db,'SELECT (SELECT count(*) FROM restaurants),(SELECT count(*) FROM menu_items),(SELECT count(*) FROM customers),(SELECT count(*) FROM order_items);'))
