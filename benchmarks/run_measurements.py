"""Real HTTP/SQL measurements. No fabricated latency or query-count inputs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
import csv
import http.client
import json
import math
import statistics
import subprocess
import time
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'benchmarks/results'
CONTAINER = 'onlineorder-resume-benchmark-db'
PORTS = {'baseline':18080,'optimized':18081,'cached':18082}
DATABASES = {'baseline':'onlineorder_baseline','optimized':'onlineorder_optimized','cached':'onlineorder_optimized'}
TABLES = ('customers','carts','order_items','menu_items','restaurants')

def sql(db, statement):
    result = subprocess.run(['docker','exec','-i',CONTAINER,'psql','-X','-U','postgres','-d',db,'-At','-v','ON_ERROR_STOP=1'],input=statement,text=True,capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()

def reset_stats():
    sql('postgres','SELECT pg_stat_statements_reset();')

def query_counts(db):
    rows=json.loads(sql('postgres',f"SELECT COALESCE(json_agg(t),'[]') FROM (SELECT query,calls FROM pg_stat_statements WHERE dbid=(SELECT oid FROM pg_database WHERE datname='{db}')) t;"))
    selected=[r for r in rows if r['query'].lstrip().lower().startswith('select') and any(('"'+name+'"') in r['query'].lower() or ('from '+name) in r['query'].lower() for name in TABLES)]
    return {'total':sum(r['calls'] for r in selected),'statements':selected}

def login(port,user):
    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=30)
    conn.request('POST','/login',body=urlencode({'username':f'bench{user}@example.test','password':'benchmark-pass'}),headers={'Content-Type':'application/x-www-form-urlencoded'})
    response=conn.getresponse();response.read()
    assert response.status==200, (port,user,response.status)
    cookie=SimpleCookie();cookie.load(response.getheader('Set-Cookie',''))
    assert 'JSESSIONID' in cookie
    conn.close()
    return 'JSESSIONID='+cookie['JSESSIONID'].value

def request_batch(name,cookies,requests=1000,workers=20):
    assert requests%workers==0
    start=time.perf_counter()
    def worker(index):
        conn=http.client.HTTPConnection('127.0.0.1',PORTS[name],timeout=30)
        measurements=[]
        try:
            for i in range(requests//workers):
                user=1+index+workers*(i%5)
                began=time.perf_counter_ns()
                conn.request('GET','/cart',headers={'Cookie':cookies[user],'Connection':'keep-alive'})
                response=conn.getresponse();body=response.read()
                elapsed=(time.perf_counter_ns()-began)/1e6
                assert response.status==200,(name,response.status,body[:300])
                cart=json.loads(body)
                assert cart['id']==user and len(cart['order_items'])==50 and cart['total_price']==512.5,cart
                measurements.append({'user':user,'ms':elapsed,'bytes':len(body),'status':response.status})
        finally:
            conn.close()
        return measurements
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows=[r for group in pool.map(worker,range(workers)) for r in group]
    return rows,time.perf_counter()-start

def percentile(values,q):
    ordered=sorted(values)
    return ordered[max(0,math.ceil(len(ordered)*q)-1)]

def http_benchmarks():
    cookies={}
    for name,port in PORTS.items():
        with ThreadPoolExecutor(max_workers=10) as pool:
            values=list(pool.map(lambda user:login(port,user),range(1,101)))
        cookies[name]=dict(zip(range(1,101),values))
        request_batch(name,cookies[name],requests=1000)
        print('JVM warmup and 100 authenticated sessions ready:',name,flush=True)
    all_results=[]
    orders=[['baseline','optimized','cached'],['cached','baseline','optimized'],['optimized','cached','baseline']]
    for trial,order in enumerate(orders,1):
        for name in order:
            # Exercise every user's cart immediately before measurement, including warm-cache runs.
            request_batch(name,cookies[name],requests=200)
            reset_stats()
            rows,seconds=request_batch(name,cookies[name],requests=1000)
            counts=query_counts(DATABASES[name])
            result={'name':name,'trial':trial,'requests':len(rows),'concurrency':20,'users':100,'cart_lines':50,
                    'duration_seconds':seconds,'requests_per_second':len(rows)/seconds,
                    'p50_ms':percentile([r['ms'] for r in rows],.5),'p95_ms':percentile([r['ms'] for r in rows],.95),
                    'p99_ms':percentile([r['ms'] for r in rows],.99),'errors':sum(r['status']!=200 for r in rows),'sql':counts}
            all_results.append(result)
            with (OUT/f'http-{name}-{trial}.csv').open('w') as f:
                writer=csv.DictWriter(f,fieldnames=['user','ms','bytes','status']);writer.writeheader();writer.writerows(rows)
            (OUT/'http-results.json').write_text(json.dumps(all_results,indent=2))
            print(name,'trial',trial,'P95',round(result['p95_ms'],3),'ms, SQL',counts['total'],flush=True)
    reset_stats()
    conn=http.client.HTTPConnection('127.0.0.1',18081,timeout=30)
    conn.request('GET','/restaurants/menu');response=conn.getresponse();body=response.read();conn.close()
    assert response.status==200 and len(json.loads(body))==100
    catalog={'restaurants':100,'menu_items':10000,'response_bytes':len(body),'sql':query_counts('onlineorder_optimized')}
    (OUT/'catalog-query-count.json').write_text(json.dumps(catalog,indent=2))
    assert catalog['sql']['total']==2,catalog
    return all_results

def index_benchmarks():
    db='onlineorder_index'
    queries={
        'cart_items': 'SELECT * FROM order_items WHERE cart_id=50',
        'existing_cart_item': 'SELECT * FROM order_items WHERE cart_id=50 AND menu_item_id=4901',
        'restaurant_menu': 'SELECT * FROM menu_items WHERE restaurant_id=50',
    }
    expected={'cart_items':50,'existing_cart_item':1,'restaurant_menu':100}
    raw=[]
    for trial,states in enumerate([['without','with'],['with','without'],['without','with']],1):
        for state in states:
            if state=='without':
                sql(db,'DROP INDEX IF EXISTS idx_menu_items_restaurant; DROP INDEX IF EXISTS uq_order_items_cart_menu; ANALYZE;')
            else:
                sql(db,(ROOT/'src/main/resources/query-indexes.sql').read_text()+'\nANALYZE;')
            for label,query in queries.items():
                # Warm PostgreSQL buffers, then collect 30 plans in a single psql connection.
                sql(db,'\n'.join('EXPLAIN (ANALYZE,BUFFERS,TIMING OFF,FORMAT JSON) '+query+';' for _ in range(10)))
                output=sql(db,'\n'.join('EXPLAIN (ANALYZE,BUFFERS,TIMING OFF,FORMAT JSON) '+query+';' for _ in range(30)))
                decoder=json.JSONDecoder();offset=0
                while offset<len(output):
                    while offset<len(output) and output[offset].isspace():offset+=1
                    if offset>=len(output):break
                    plan,end=decoder.raw_decode(output,offset);offset=end
                    assert plan[0]['Plan']['Actual Rows']==expected[label],plan
                    raw.append({'trial':trial,'index':state,'query':label,'plan':plan[0]})
                selected=[r['plan']['Execution Time'] for r in raw if r['trial']==trial and r['index']==state and r['query']==label]
                print('Index',state,label,'trial',trial,'median',statistics.median(selected),'ms',flush=True)
                (OUT/'index-plans.json').write_text(json.dumps(raw,indent=2))
    summaries={}
    for label in queries:
        summaries[label]={state:{'samples':len(values),'median_execution_ms':statistics.median(values),'p95_execution_ms':percentile(values,.95)}
                          for state in ['without','with']
                          for values in [[r['plan']['Execution Time'] for r in raw if r['query']==label and r['index']==state]]}
    (OUT/'index-results.json').write_text(json.dumps(summaries,indent=2))
    return summaries

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    sql('postgres','CREATE EXTENSION IF NOT EXISTS pg_stat_statements;')
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('suite',choices=['http','index','all'],default='all',nargs='?');args=parser.parse_args()
    if args.suite in ['http','all']:http_benchmarks()
    if args.suite in ['index','all']:index_benchmarks()
