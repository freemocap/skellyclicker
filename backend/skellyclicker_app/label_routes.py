"""Label execution endpoints; lifecycle and status transport come from the SDK."""
import json
from pathlib import Path
import threading
from fastapi import APIRouter,HTTPException
import pyarrow.parquet as pq
from freemocap_sdk.pipeline import PipelineRun,PipelineRegistry,pipeline_router
from freemocap_sdk.storage import atomic_json,resolve_relative,file_digest
from .job_lifecycle import jobs,guard,busy
from .label_inputs import PreviewLabels,GenerateLabels,StaleInputs,bind_inputs,preview,checked
from .label_pipeline import GRAPH,handlers
from .projects import Project,read_model,recording_structure

router=APIRouter(prefix='/api/labels')
registry=PipelineRegistry()
task_router=pipeline_router(registry,prefix='/api/label-tasks')


@router.post('/preview')
def preview_labels(request:PreviewLabels):
    try:return {**preview(request),'graph':GRAPH.model_dump(mode='json')}
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error


class RunCancellation:
    def __init__(self,run):self.run=run
    def set(self):self.run.cancel()
    def is_set(self):return self.run.snapshot()['cancel_requested']


@router.post('/runs',status_code=202)
def start_labels(request:GenerateLabels):
    with guard:
        if busy():raise HTTPException(409,'Another preparation or label run is active')
        try:bound=bind_inputs(request)
        except StaleInputs as error:raise HTTPException(409,str(error)) from error
        except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error
        job={}
        def observe(snapshot):
            job['status']={'job_id':snapshot['run_id'],'state':snapshot['status'],'stage':'label generation',**snapshot}
            atomic_json(job['work']/'status.json',snapshot)
        run=PipelineRun(GRAPH,labels={'bind_inputs':'Bind verified inputs','choose_moments':'Choose paired moments','project_labels':'Project candidate labels','publish_candidates':'Save unreviewed candidates'},on_snapshot=observe)
        work=recording_structure(bound.root,bound.recording.recording_id).application_dir('skellyclicker')/'working'/'labels'/run.run_id
        work.mkdir(parents=True)
        job.update(root=bound.root,manifest=bound.manifest,work=work,output=work/'output',request=request.model_dump(mode='json'),
                   status={'job_id':run.run_id,'state':'queued','stage':'label generation'},cancel=RunCancellation(run),process=None,run=run)
        atomic_json(work/'request.json',request.model_dump(mode='json'))
        registry.add(run)
        def execute():
            run.execute(handlers(request,work,run.run_id),resource_capacity={'compute':1})
        thread=threading.Thread(target=execute,name='skellyclicker-label-job',daemon=False)
        job['thread']=thread;jobs[run.run_id]=job;thread.start()
        return {'run_id':run.run_id,'status_url':f'/api/label-tasks/{run.run_id}','result_url':f'/api/labels/runs/{run.run_id}/result'}


def result_view(manifest:Path, result_path=None):
    project=read_model(manifest,Project)
    selected=result_path or project.label_result
    if not selected:return None
    folder=resolve_relative(manifest.parent,selected)
    metadata=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for name,identity in metadata['files'].items():checked(resolve_relative(folder,name),identity)
    moments=pq.read_table(folder/'moments.parquet').to_pylist()
    for moment in moments:moment['timestamp_ns']=str(moment['timestamp_ns'])
    # Source frame is mapped to the actual playback sample list, never a constant offset.
    poses=pq.read_table(resolve_relative(manifest.parent,metadata['pose_result'])/'timing.parquet',columns=['source_frame']).column('source_frame').to_pylist()
    indices={frame:i for i,frame in enumerate(poses)}
    for moment in moments:moment['playback_frame']=indices.get(moment['source_frame'])
    return {'path':selected,'manifest_sha256':file_digest(folder/'manifest.json'),'manifest':metadata,'moments':moments,
            'playback_id':Path(project.playback_result).name if project.playback_result else None}


@router.get('/result')
def selected_labels(project_path:str):
    try:return result_view(Path(project_path).resolve())
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error


@router.get('/runs/{run_id}/result')
def run_result(run_id:str):
    try:run=registry.get(run_id)
    except KeyError as error:raise HTTPException(404,'Unknown label run') from error
    snapshot=run.snapshot()
    if snapshot['status']!='complete':return {'status':snapshot['status'],'result':None}
    return {'status':'complete','result':result_view(jobs[run_id]['manifest'],run.result.outputs['publish_candidates']['result']['path'])}

# Selection is a retained human browsing decision, never label approval.
from pydantic import Field
from uuid import uuid4
import pyarrow as pa
from freemocap_sdk.storage import project_lock,publish_directory
from .projects import Model

class SelectMoment(Model):
    project_path:str
    expected_label_manifest_sha256:str
    expected_selection_sha256:str|None=None
    moment_id:str
    source_frame:int=Field(ge=0)
    timestamp_ns:str=Field(pattern='^[0-9]+$')
    selected:bool


def selection_view(manifest):
    project=read_model(manifest,Project)
    if not project.active_review:return {'sha256':None,'selected_moment_ids':[],'review_state':'unreviewed'}
    folder=resolve_relative(manifest.parent,project.active_review)
    metadata=json.loads((folder/'manifest.json').read_text())
    checked(folder/'selection.parquet',metadata['files']['selection.parquet'])
    return {'sha256':file_digest(folder/'manifest.json'),'selected_moment_ids':pq.read_table(folder/'selection.parquet').column('moment_id').to_pylist(),'review_state':'unreviewed'}


@router.get('/selection')
def selected_moments(project_path:str):
    try:return selection_view(Path(project_path).resolve())
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error


@router.post('/selection')
def save_selection(request:SelectMoment):
    manifest=Path(request.project_path).resolve()
    try:
        with guard:
            if busy():raise HTTPException(409,'A preparation or label run is active')
            with project_lock(manifest.parent):
                result=result_view(manifest)
                if not result or result['manifest_sha256']!=request.expected_label_manifest_sha256:raise HTTPException(409,'Generated labels changed; reload before selecting')
                project=read_model(manifest,Project)
                if project.sample_result!=result['manifest']['pose_result'] or not project.target_manifests or file_digest(resolve_relative(manifest.parent,project.target_manifests[0]))!=result['manifest']['target_manifest_sha256']:
                    raise HTTPException(409,'Current pose or target selection differs from these labels')
                current=selection_view(manifest)
                if current['sha256']!=request.expected_selection_sha256:raise HTTPException(409,'Selection changed; reload before selecting')
                moment=next((row for row in result['moments'] if row['moment_id']==request.moment_id),None)
                if not moment or moment['source_frame']!=request.source_frame or moment['timestamp_ns']!=request.timestamp_ns:raise HTTPException(422,'Presented source identity does not match a generated moment')
                selected=set(current['selected_moment_ids'])
                if request.selected:selected.add(request.moment_id)
                else:selected.discard(request.moment_id)
                rows=[r for r in result['moments'] if r['moment_id'] in selected]
                revision='selection-'+uuid4().hex[:12]
                extension=recording_structure(manifest.parent,result['manifest']['recording_id']).application_dir('skellyclicker')
                staged=extension/'working'/'reviews'/revision;staged.mkdir(parents=True)
                schema=pa.schema([('moment_id',pa.string()),('source_frame',pa.int64()),('timestamp_ns',pa.int64())])
                table=pa.Table.from_pylist([{'moment_id':r['moment_id'],'source_frame':r['source_frame'],'timestamp_ns':int(r['timestamp_ns'])} for r in rows],schema=schema)
                pq.write_table(table,staged/'selection.parquet')
                atomic_json(staged/'manifest.json',{'schema_version':1,'label_result':result['path'],'label_manifest_sha256':result['manifest_sha256'],
                    'previous_selection_sha256':current['sha256'],'review_state':'unreviewed','meaning':'Selected for review; not approved labels',
                    'files':{'selection.parquet':{'sha256':file_digest(staged/'selection.parquet'),'bytes':(staged/'selection.parquet').stat().st_size}}})
                destination=extension/'reviews'/revision;destination.parent.mkdir(parents=True,exist_ok=True)
                publish_directory(staging=staged,destination=destination)
                project=read_model(manifest,Project);project.active_review=destination.relative_to(manifest.parent).as_posix()
                atomic_json(manifest,project.model_dump(mode='json'))
                return selection_view(manifest)
    except HTTPException:raise
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error
