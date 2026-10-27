"""Integration checks against the named loopback test workspace; no real mill data."""
import requests,json
base='http://127.0.0.1:5173'
session=requests.Session()
def check(name,condition):
    assert condition,name
    print('PASS',name,flush=True)
def post(action,data=None,**extra):
    return session.post(base+'/api/workspace',json=dict(action=action,data=data,**extra),headers={'Origin':base},timeout=40)
r=requests.get(base+'/api/workspace',timeout=40);check('anonymous API rejected',r.status_code==401)
r=requests.post(base+'/api/workspace',json={'action':'mill','data':{}},headers={'Origin':base},timeout=40);check('anonymous write rejected',r.status_code==401)
r=session.get(base+'/signin-with-chatgpt?return_to=/portal',timeout=40);check('local test sign-in',r.status_code==200)
r=session.get(base+'/api/workspace',timeout=40);check('signed-in workspace readable',r.status_code==200)
check('other-owner records hidden',all(x['id']!='other-owner-plot' for x in r.json()['plots']) and all(x['id']!='other-owner-sample' for x in r.json()['samples']))
check('local QA workspace reset',post('erase',confirmation='ERASE').status_code==200 if r.json().get('mill') else True)
r=post('mill',{'name':'QA Test Mill','location':'Local test only','season':'2026-27'});check('mill profile persisted',r.status_code==200)
plot={'plotNo':'QA-001','village':'Test cluster','variety':'CO-265','caneType':'Suru','area':1.5,'plantingDate':'2025-11-01'}
r=post('plot',plot);check('plot created',r.status_code==200)
r=post('plot',plot);check('duplicate plot rejected',r.status_code==409)
w=session.get(base+'/api/workspace',timeout=40).json();p=next(x for x in w['plots'] if x['plotNo']=='QA-001')
r=post('sample',{'plotId':p['id'],'sampleDate':'2026-10-05','pol':18,'brix':15});check('Pol above Brix rejected',r.status_code==400)
r=post('sample',{'plotId':'other-owner-plot','sampleDate':'2026-10-05','pol':13,'brix':16});check('unowned plot sample rejected',r.status_code==404)
r=post('plan',{'id':'other-owner-plot','harvestDate':'2026-11-15','priority':'Ready'});check('unowned plot plan rejected',r.status_code==404)
r=post('observation',{'id':'other-owner-plot','acquisitionDate':'2026-10-05','cloud':5,'ndvi':0.7});check('other-owner observation rejected',r.status_code==404)
r=post('deletePlot',id='other-owner-plot');check('other-owner delete returns without disclosure',r.status_code==200)
r=post('deleteSample',id='other-owner-sample');check('other-owner sample deletion returns without disclosure',r.status_code==200)
r=post('sample',{'plotId':p['id'],'sampleDate':'2026-10-05','pol':13.4,'brix':16.2,'recovery':9.6});check('lab sample persisted',r.status_code==200)
r=post('observation',{'id':p['id'],'acquisitionDate':'2026-10-05','cloud':5,'ndvi':0.71});check('observation persisted',r.status_code==200)
r=post('plan',{'id':p['id'],'harvestDate':'2026-11-15','priority':'Ready'});check('harvest plan persisted',r.status_code==200)
r=post('plot',{**plot,'plotNo':'INVALID','plantingDate':'2025-02-30'});check('invalid calendar date rejected',r.status_code==400)
r=session.post(base+'/api/workspace',json={'action':'mill','data':{'name':'Bad','location':'Bad','season':'Bad'}},headers={'Origin':'https://other-origin.example'},timeout=40);check('cross-origin write rejected',r.status_code==403)
r=post('import',[{**plot,'plotNo':'QA-002'},{**plot,'plotNo':'QA-003'}]);check('CSV batch persisted',r.status_code==200)
w=requests.Session();w.cookies.update(session.cookies);stored=w.get(base+'/api/workspace',timeout=40).json();check('new session reads saved records',len(stored['plots'])==3 and len(stored['samples'])==1)
p=next(x for x in stored['plots'] if x['plotNo']=='QA-001');check('saved observation and plan read back',p['ndvi']==.71 and p['harvestDate']=='2026-11-15')
r=post('deletePlot',id=p['id']);check('test plot and linked sample removed',r.status_code==200 and not session.get(base+'/api/workspace',timeout=40).json()['samples'])
r=post('erase',confirmation='ERASE');check('local test workspace erased',r.status_code==200)
print('All API integration checks passed. Only disposable local test records were used.')
