import os
from pathlib import Path
from fastapi import APIRouter,HTTPException
from pydantic import Field, model_validator
from .training_inputs import TrainingInputs,training_input_preview
from .training_pipeline import GRAPH

router=APIRouter(prefix='/api/training')
class TrainingRequest(TrainingInputs):
    python_path:str=''
    epochs:int=Field(default=10,ge=1,le=10000)
    batch_size:int=Field(default=2,ge=1,le=32)
    save_every:int=Field(default=1,ge=1,le=1000)
    seed:int=Field(default=20261105,ge=0,le=2147483647)
    max_seconds:int=Field(default=900,ge=30,le=86400)
    parent_run_id:str|None=None
    parent_checkpoint:str|None=None
    parent_checkpoint_sha256:str|None=Field(default=None,pattern='^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def complete_parent(self):
        fields=(self.parent_run_id,self.parent_checkpoint,self.parent_checkpoint_sha256)
        if any(v is not None for v in fields) and not all(v is not None for v in fields):raise ValueError('Select a run and checkpoint together')
        return self


@router.get('/configuration')
def configuration():
    candidates=[os.environ.get('SKELLYCLICKER_TRAINING_PYTHON',''),str(Path.home()/'freemocap_data/training_environments/benchy-dlc/Scripts/python.exe')]
    return {'graph':GRAPH.model_dump(mode='json'),'defaults':TrainingRequest(project_path='',python_path=next((p for p in candidates if p and Path(p).is_file()),'')).model_dump(mode='json'),'backend':'DeepLabCut 3.0.2 · ResNet-50'}

@router.post('/preview')
def preview(request:TrainingRequest):
    try:return training_input_preview(request)
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error

import json,threading,time
from uuid import UUID
from fastapi.responses import FileResponse
from freemocap_sdk.pipeline import PipelineRun
from freemocap_sdk.storage import atomic_json,resolve_relative
from .label_routes import registry,RunCancellation
from .job_lifecycle import jobs,guard,busy
from .projects import read_model,Project,Recording,recording_structure
from .training_pipeline import handlers
from .label_inputs import StaleInputs

@router.post('/runs',status_code=202)
def start(request:TrainingRequest):
    with guard:
        if busy():raise HTTPException(409,'Another preparation, labeling or training run is active')
        if not request.expected_selection_sha256 or not request.expected_label_manifest_sha256:raise HTTPException(422,'Preview the current included images before starting')
        if not Path(request.python_path).is_absolute() or not Path(request.python_path).is_file():raise HTTPException(422,'Select the isolated DLC Python executable')
        try:training_input_preview(request)
        except StaleInputs as error:raise HTTPException(409,str(error)) from error
        except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error
        manifest=Path(request.project_path).resolve();project=read_model(manifest,Project)
        recording=read_model(resolve_relative(manifest.parent,project.recording_manifests[0]),Recording);job={}
        def observe(snapshot):
            job['status']={'job_id':snapshot['run_id'],'state':snapshot['status'],'stage':'training',**snapshot}
            atomic_json(job['work']/'status.json',snapshot)
        run=PipelineRun(GRAPH,labels={'freeze_inputs':'Freeze included images','prepare_trainer':'Prepare DeepLabCut','train_model':'Train and evaluate','publish_run':'Save run artifacts'},on_snapshot=observe)
        work=recording_structure(manifest.parent,recording.recording_id).application_dir('skellyclicker')/'training-runs'/run.run_id;work.mkdir(parents=True)
        job.update(kind="training",root=manifest.parent,manifest=manifest,work=work,request=request.model_dump(mode='json'),status={'state':'queued'},cancel=RunCancellation(run),process=None,run=run,started=time.monotonic())
        atomic_json(work/'request.json',request.model_dump(mode='json'));registry.add(run)
        thread=threading.Thread(target=lambda:run.execute(handlers(request,job),resource_capacity={'compute':1}),name='skellyclicker-training',daemon=False)
        job['thread']=thread;jobs[run.run_id]=job;thread.start()
        return {'run_id':run.run_id,'snapshot':run.snapshot()}


def run_folder(project_path,run_id):
    try:UUID(run_id)
    except ValueError as error:raise HTTPException(422,'Invalid run ID') from error
    manifest=Path(project_path).resolve();project=read_model(manifest,Project)
    recording=read_model(resolve_relative(manifest.parent,project.recording_manifests[0]),Recording)
    folder=recording_structure(manifest.parent,recording.recording_id).application_dir('skellyclicker')/'training-runs'/run_id
    if not folder.is_dir():raise HTTPException(404,'Unknown training run')
    return folder

@router.get('/runs/{run_id}')
def inspect_run(run_id:str,project_path:str):
    folder=run_folder(project_path,run_id)
    if run_id in jobs:return jobs[run_id]['run'].snapshot()
    snapshot=json.loads((folder/'status.json').read_text(encoding='utf-8'))
    if snapshot['status'] in ('running','queued'):
        snapshot.update(status='failed',error='Backend stopped before the run completed; saved artifacts remain available')
    return snapshot

@router.get('/runs/{run_id}/artifact')
def artifact(run_id:str,project_path:str,path:str):
    folder=run_folder(project_path,run_id)
    try:asset=resolve_relative(folder,path)
    except ValueError as error:raise HTTPException(422,str(error)) from error
    if not asset.is_file():raise HTTPException(404,'Artifact not found')
    return FileResponse(asset)

@router.get('/runs/{run_id}/result')
def result(run_id:str,project_path:str):
    folder=run_folder(project_path,run_id);path=folder/'result.json'
    if not path.is_file():return {'result':None,'snapshot':inspect_run(run_id,project_path)}
    return {'result':json.loads(path.read_text(encoding='utf-8')),'snapshot':inspect_run(run_id,project_path)}

@router.get('/runs')
def list_runs(project_path:str):
    manifest=Path(project_path).resolve();project=read_model(manifest,Project)
    recording=read_model(resolve_relative(manifest.parent,project.recording_manifests[0]),Recording)
    root=recording_structure(manifest.parent,recording.recording_id).application_dir('skellyclicker')/'training-runs'
    records=[]
    if not root.exists():return records
    for folder in sorted(root.iterdir(),key=lambda p:p.stat().st_mtime,reverse=True):
        if not folder.is_dir() or not (folder/'status.json').is_file():continue
        snapshot=inspect_run(folder.name,project_path)
        dataset=json.loads((folder/'dataset.json').read_text(encoding='utf-8'))['manifest'] if (folder/'dataset.json').is_file() else None
        records.append({'run_id':folder.name,'status':snapshot['status'],'counts':dataset['counts'] if dataset else None,
                        'keypoint_count':len(dataset['keypoint_names']) if dataset else None,
                        'epoch':max((p['step'] for s in snapshot['metrics'] for p in s['points']),default=0)})
    return records

@router.get('/runs/{run_id}/checkpoints')
def saved_checkpoints(run_id:str,project_path:str):
    from .training_checkpoints import checkpoints
    try:return checkpoints(project_path,run_id)
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error
