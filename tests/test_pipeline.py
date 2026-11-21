from datetime import datetime
from pathlib import Path
from app.analytics import haversine_km, activity_area, quality_distance, stays, geojson_features
from app.demo_seed import create_demo_csv
from app.models import Observation
from app.pipeline import parse_row, ValidationError
import pytest


def test_wgs84_distance():
    assert haversine_km(34.0,-118.0,34.0,-118.0) == 0
    assert 110 < haversine_km(0,0,1,0) < 112


def test_reject_invalid_and_naive():
    row={"participant_id":"SYN-EX01","timestamp_utc":"2026-11-19T16:00:00Z","latitude":"34.1","longitude":"-118.2","steps":"0","source":"synthetic"}
    assert parse_row(row,2)['participant_id'] == 'SYN-EX01'
    for change in ({'latitude':'100'}, {'timestamp_utc':'2026-11-19T16:00:00'},
                   {'steps':'-1'}, {'source':'Fitbit live'}, {'heart_rate_bpm':'260'}):
        with pytest.raises(ValidationError):
            parse_row({**row,**change},2)


def test_ingest_and_idempotence(client, tmp_path):
    data = create_demo_csv(tmp_path / 'sample.csv').read_bytes()
    r = client.post('/api/import',files={'file':('sample.csv',data,'text/csv')})
    assert r.status_code == 200
    report=r.json()
    assert report['accepted'] == 366
    assert report['rejected'] == 0
    assert client.get('/api/summary').json()['participant_days'] == 6
    rerun=client.post('/api/import',files={'file':('sample.csv',data,'text/csv')}).json()
    assert rerun['duplicates'] == 366
    assert rerun['accepted'] == 0
    assert client.get('/api/summary').json()['observations'] == 366


def test_geo_analysis_and_export(client,tmp_path):
    data = create_demo_csv(tmp_path/'demo.csv').read_bytes()
    client.post('/api/import',files={'file':('demo.csv',data,'text/csv')})
    ppl=client.get('/api/participants').json()
    assert len(ppl)==3 and ppl[0]['days']==2
    stats=client.get('/api/participants/SYN-P001/daily').json()
    assert len(stats)==2 and stats[0]['distance_km']>0
    geo=client.get('/api/participants/SYN-P001/geojson?date=2026-11-16').json()
    kinds={f['properties']['kind'] for f in geo['features']}
    assert {'route','start','end','stay','activity_area'}.issubset(kinds)
    areas=[f for f in geo['features'] if f['properties']['kind']=='activity_area']
    assert areas[0]['properties']['area_km2']>0
    stays_result=client.get('/api/participants/SYN-P001/stays?date=2026-11-16').json()
    assert len(stays_result)>=2
    export=client.get('/api/participants/SYN-P001/export.csv?date=2026-11-16')
    assert export.status_code==200 and len(export.text.splitlines())==62


def test_import_bad_and_metadata(client):
    wrong=b'participant_id,latitude\nfoo,100\n'
    result=client.post('/api/import',files={'file':('bad.csv',wrong,'text/csv')})
    assert result.status_code == 422
    assert client.get('/api/imports').json()==[]
    assert client.post('/api/import',files={'file':('bad.txt',b'xyz','text/plain')}).status_code==415
    assert client.get('/api/participants/nope/geojson').status_code==404
    assert client.get('/api/health').json()['data_policy']=='SYNTHETIC_ONLY'


def test_speed_outlier_flagged():
    def make(i,lat,lon):
        return Observation(participant_id='SYN-X',timestamp_utc=datetime(2026,1,1,0,i),latitude=lat,longitude=lon,steps=0,source='synthetic')
    trace=[make(0,34,-118),make(5,35,-118),make(10,35.0001,-118)]
    distance,outliers=quality_distance(trace)
    assert outliers==1 and 0<distance<0.05
    geo=geojson_features(trace,include_area=False)
    routes=[f for f in geo['features'] if f['properties']['kind']=='route']
    assert len(routes)==1 and len(routes[0]['geometry']['coordinates'])==2


def test_rejection_counters(client):
    raw="""participant_id,timestamp_utc,latitude,longitude,steps,heart_rate_bpm,source
SYN-P001,2026-11-19T16:00:00Z,34,-118,4,80,synthetic
SYN-P001,2026-11-19T16:00:00Z,34,-118,4,80,synthetic
SYN-P002,2026-11-19T16:10:00Z,999,-118,4,80,synthetic
SYN-P003,2026-11-19T16:20:00Z,34,-118,4,80,real-device
""".encode()
    report=client.post('/api/import',files={'file':('check.csv',raw,'text/csv')}).json()
    assert (report['accepted'],report['duplicates'],report['rejected'])==(1,1,2)
    assert len(report['errors'])==2


def test_upload_limit(client, monkeypatch):
    monkeypatch.setenv('MAX_UPLOAD_BYTES','5')
    resp=client.post('/api/import',files={'file':('x.csv',b'123456','text/csv')})
    assert resp.status_code==413
