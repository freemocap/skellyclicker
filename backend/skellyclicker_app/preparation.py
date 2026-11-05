"""App-owned bounded fresh preparation; SDK owns storage and server primitives."""
import importlib.resources
import json
import logging
import os
from pathlib import Path
import queue
import subprocess
import threading
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from freemocap_sdk.storage import atomic_json, inventory, resolve_relative, project_lock, publish_directory, file_digest
from .projects import Project, Recording, read_model, open_project

router = APIRouter(prefix='/api/preparation')
logger = logging.getLogger('skellyclicker.preparation')
_jobs = {}
_guard = threading.RLock()

class PreparationRequest(BaseModel):
    project_path: str
    start_frame: int = Field(default=0, ge=0)
    frame_count: int = Field(default=30, ge=1, le=60)


def runtime_config():
    base = Path(os.environ.get('SKELLYCLICKER_ZED_RUNTIME', str(Path.home()/'AppData/Local/ZEDBenchy')))
    cuda = list((base/'cuda12-runtime').rglob('cudart64_12.dll'))
    return {'zed_python': str(base/'.venv/Scripts/python.exe'),
            'pose_python': str(base/'pose-env/Scripts/python.exe'),
            'zed_dlls': [os.environ.get('SKELLYCLICKER_ZED_SDK_BIN', 'C:/Program Files (x86)/ZED SDK/bin')] + list(dict.fromkeys(str(p.parent) for p in cuda)),
            'pose_dlls': os.environ.get('SKELLYCLICKER_POSE_DLLS', str(Path.home()/'code-stuff/codeberg/jonmatthis/playground/happypose/local_data/windows-env/Lib/site-packages/torch/lib'))}

@router.get('/runtime')
def runtime():
    config = runtime_config()
    missing = [p for p in [config['zed_python'],config['pose_python'],config['pose_dlls'],*config['zed_dlls']] if not Path(p).exists()]
    if len(config['zed_dlls']) < 2: missing.append('CUDA 12 runtime DLL directory')
    return {'available': not missing, 'missing': missing}


def update(job, **values):
    with _guard:
        job['status'].update(values, updated_at=datetime.now(timezone.utc).isoformat())
        atomic_json(job['work']/'status.json',job['status'])


def terminate_owned(process):
    if process.poll() is None:
        if os.name == 'nt':
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        else: process.terminate()
        process.wait(timeout=15)


def run_worker(job, name, interpreter):
    source = importlib.resources.files('skellyclicker_app').joinpath('workers',name+'.worker').read_text(encoding='utf-8-sig')
    script = job['work']/(name+'.py');script.write_text(source,encoding='utf-8')
    # Frozen Windows DLL search paths must not leak into independent Python runtimes.
    env = {k:v for k,v in os.environ.items() if not k.startswith('_PYI') and k not in ('_MEIPASS2','PYTHONHOME','PYTHONPATH')}
    frozen = os.name == 'nt' and hasattr(sys, '_MEIPASS')
    if frozen:
        import ctypes
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    try:
        process = subprocess.Popen([interpreter,'-u',str(script),str(job['work']/'request.json')],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors='replace',env=env,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    finally:
        if frozen: ctypes.windll.kernel32.SetDllDirectoryW(str(sys._MEIPASS))
    job['process'] = process
    lines = queue.Queue()
    def read():
        for line in process.stdout: lines.put(line.rstrip())
        lines.put(None)
    reader=threading.Thread(target=read,daemon=True);reader.start();cancel_at=None
    try:
        with (job['work']/(name+'.log')).open('w',encoding='utf-8') as log:
            while True:
                if job['cancel'].is_set():
                    (job['output']/'cancel').touch()
                    cancel_at = cancel_at or time.monotonic()
                    if time.monotonic()-cancel_at>10: terminate_owned(process)
                try: line=lines.get(timeout=.2)
                except queue.Empty:
                    if process.poll() is not None and not reader.is_alive(): break
                    continue
                if line is None: break
                log.write(line+'\n');log.flush()
                if line.startswith('SKELLY_PROGRESS '):
                    values=json.loads(line[len('SKELLY_PROGRESS '):]);update(job,**values)
                    logger.info('%s: %s',name,values)
                else: logger.info('%s: %s',name,line)
        code=process.wait()
        if job['cancel'].is_set(): raise InterruptedError('Preparation cancelled')
        if code: raise RuntimeError(f'{name} failed with exit code {code}; see live logs')
    finally:
        terminate_owned(process);reader.join(timeout=3);process.stdout.close();job['process']=None


def publish_result(job):
    import pyarrow as pa
    import pyarrow.parquet as pq
    output=job['output'];request=job['request'];rows=json.loads((output/'candidates.json').read_text())
    if len(rows)!=request['frame_count'] or [r['source_frame'] for r in rows]!=list(range(request['start_frame'],request['start_frame']+request['frame_count'])):
        raise ValueError('Candidate rows do not match requested source range')
    timestamps=[r['timestamp_ns'] for r in rows]
    if any(b<=a for a,b in zip(timestamps,timestamps[1:])): raise ValueError('Non-increasing source timestamps')
    calibration=json.loads((output/'calibration.json').read_text())
    descriptor={'schema_version':1,'recording_id':request['recording_id'],'target_sha256':request['target_sha256'],'source_sha256':request['source_sha256'],'calibration':calibration,'geometry':json.loads((output/'geometry.json').read_text()),'mask_preset':request['mask_preset'],'human_review':'unreviewed','pose_units':'m','pose_frame':'original STL to rectified camera (x right, y down, z forward)'}
    fields=sorted(set().union(*(row.keys() for row in rows))-{'camera_ids'})
    table=pa.table({key:pa.array([row.get(key) for row in rows]) for key in fields})
    table=table.replace_schema_metadata({b'skellyclicker.candidates':json.dumps(descriptor,allow_nan=False).encode()})
    pq.write_table(table,output/'candidates.parquet')
    timing=pa.table({'source_frame':pa.array([r['source_frame'] for r in rows],type=pa.int64()),'timestamp_ns':pa.array(timestamps,type=pa.int64())})
    pq.write_table(timing.replace_schema_metadata({b'skellyclicker.timing':json.dumps({'clock_id':'zed-image-clock','unit':'ns','recording_id':request['recording_id']}).encode()}),output/'timing.parquet')
    summary={'job_id':job['status']['job_id'],'frames':[{k:v for k,v in r.items() if 'pose' not in k and not k.startswith('T_')} for r in rows],'accepted':sum(r['accepted'] for r in rows),'calibration':calibration,'human_review':'unreviewed','mask_preset':request['mask_preset']}
    atomic_json(output/'summary.json',summary)
    atomic_json(output/'provenance.json',{'request':request,'worker_sha256':{name:file_digest(job['work']/(name+'.py')) for name in ('zed_replay','fit_pose')},'replay':json.loads((output/'replay-software.json').read_text()),'pose':json.loads((output/'pose-software.json').read_text())})
    atomic_json(output/'manifest.json',{'schema_version':1,'descriptor':descriptor,'numerical_authority':['candidates.parquet','timing.parquet'],'derived_review_index':'summary.json','files':{k:v.model_dump() for k,v in inventory(output).items()}})
    root=job['root'];relative=f"results/{request['recording_id']}/{job['status']['job_id']}/r001"
    destination=resolve_relative(root,relative);destination.parent.mkdir(parents=True,exist_ok=True)
    with project_lock(root):
        if job['cancel'].is_set(): raise InterruptedError('Preparation cancelled before publication')
        project=read_model(job['manifest'],Project)
        publish_directory(staging=output,destination=destination)
        project.sample_result=relative
        atomic_json(job['manifest'],project.model_dump(mode='json'))
    update(job,stage='encoding playback')
    from .playback_adapter import build_project_playback
    build_project_playback(job['manifest'], cancelled=job['cancel'].is_set)
    update(job,state='complete',stage='complete',completed=len(rows),total=len(rows),accepted=summary['accepted'],result=relative)
    logger.info('Fresh sample result ready: %d frames, %d passed pilot gates (not human approved)',len(rows),summary['accepted'])


def execute(job):
    try:
        update(job,state='running',stage='replay')
        run_worker(job,'zed_replay',job['request']['runtime']['zed_python'])
        update(job,stage='fit',completed=0)
        run_worker(job,'fit_pose',job['request']['runtime']['pose_python'])
        update(job,stage='publishing');publish_result(job)
    except InterruptedError as error: update(job,state='cancelled',error=str(error))
    except Exception as error:
        logger.exception('Fresh preparation failed');update(job,state='failed',error=str(error))

@router.post('/start')
def start(request: PreparationRequest):
    with _guard:
        if any(j['status']['state'] in ('queued','running','cancelling') for j in _jobs.values()): raise HTTPException(409,'A preparation job is already active')
        readiness=runtime()
        if not readiness['available']: raise HTTPException(422,readiness)
        view=open_project(Path(request.project_path))
        if view['issues']: raise HTTPException(422,view['issues'])
        if len(view['recordings'])!=1 or len(view['targets'])!=1: raise HTTPException(422,'Select a project with one recording and one target for this first preparation workflow')
        root=Path(view['root']);recording=view['recordings'][0];target=view['targets'][0]
        job_id='sample-'+uuid4().hex[:12];work=root/'working/preparation'/job_id;output=work/'output';output.mkdir(parents=True)
        config={**request.model_dump(),'recording_id':recording['recording_id'],'source_svo':recording['source']['path'],'source_sha256':recording['source']['sha256'],'stl':str(resolve_relative(root,target['geometry']['path'])),'target_sha256':target['geometry']['sha256'],'stl_units':target['authored_units'],'mask_preset':'benchy_recording_hsv_v1','runtime':runtime_config(),'output':str(output)}
        atomic_json(work/'request.json',config)
        job={'root':root,'manifest':Path(view['manifest_path']),'work':work,'output':output,'request':config,'status':{'job_id':job_id,'state':'queued','stage':'queued','completed':0,'total':request.frame_count},'cancel':threading.Event(),'process':None}
        _jobs[job_id]=job;update(job)
        thread=threading.Thread(target=execute,args=(job,),daemon=True);job['thread']=thread;thread.start()
        return dict(job['status'])

@router.get('/status/{job_id}')
def status(job_id: str):
    with _guard:
        if job_id not in _jobs: raise HTTPException(404,'Job not present in this backend session; retained attempts are not automatically resumed')
        return dict(_jobs[job_id]['status'])

@router.post('/cancel/{job_id}')
def cancel(job_id: str):
    with _guard:
        if job_id not in _jobs: raise HTTPException(404,'Unknown job')
        job=_jobs[job_id]
        if job['status']['state'] in ('queued','running','cancelling'):
            job['cancel'].set();update(job,state='cancelling')
        return dict(job['status'])


def selected_result(project_path):
    path=Path(project_path).resolve()
    if path.is_dir():
        matches=list(path.glob('*_project.json'))
        if len(matches)!=1: raise HTTPException(422,'Choose the project manifest')
        path=matches[0]
    project=read_model(path,Project)
    return resolve_relative(path.parent,project.sample_result) if project.sample_result else None

@router.get('/result')
def result(project_path: str):
    folder=selected_result(project_path)
    return json.loads((folder/'summary.json').read_text()) if folder else None

@router.get('/image')
def image(project_path: str, frame: int, view: str):
    if view not in ('left','right','left-candidate','right-candidate','depth','mask'): raise HTTPException(422,'Unknown view')
    folder=selected_result(project_path)
    if folder is None: raise HTTPException(404,'No prepared result')
    summary=json.loads((folder/'summary.json').read_text())
    if frame not in [r['source_frame'] for r in summary['frames']]: raise HTTPException(404,'Frame outside result')
    return FileResponse(folder/'frames'/f'{frame:06d}-{view}.png',media_type='image/png')


def shutdown_jobs():
    for job in list(_jobs.values()):
        if job['thread'].is_alive():
            job['cancel'].set()
            if job['process'] is not None: terminate_owned(job['process'])
            job['thread'].join(timeout=5)
