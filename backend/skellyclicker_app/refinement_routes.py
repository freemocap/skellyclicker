"""Model-guided proposals remain separate from the reviewed training dataset."""
import json,threading,time,shutil
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import Field,model_validator
from freemocap_sdk.pipeline import GraphNode,GraphDefinition,compile_graph,PipelineRun
from freemocap_sdk.storage import atomic_json,file_digest,resolve_relative
from .projects import Model,Project,read_model,recording_structure
from .label_inputs import PreviewLabels,GenerateLabels,bind_inputs
from .label_routes import registry,RunCancellation,result_view,selection_view,start_labels
from .label_pipeline import projection_source
from .training_checkpoints import bind_parent,folder_for
from .training_routes import TrainingRequest
from .training_pipeline import run_worker
from .job_lifecycle import jobs,guard,busy

router=APIRouter(prefix='/api/refinement')
GRAPH=compile_graph(GraphDefinition(nodes=(GraphNode(id='mine_examples',operation='mine_examples',effects=('read_record','write_disk')),),edges=()))
class MineRequest(TrainingRequest):
    image_limit:int=Field(default=30,ge=1,le=200)
    spacing_seconds:float=Field(default=.5,ge=0,le=60)
    confidence_threshold:float=Field(default=.2,ge=0,le=1)
    near_error_threshold:float=Field(default=.03,gt=0,le=1)
    major_error_threshold:float=Field(default=.5,gt=0,le=10)
    @model_validator(mode='after')
    def selected_checkpoint(self):
        if not self.parent_run_id:raise ValueError('Select a saved checkpoint before finding new examples')
        if self.major_error_threshold<=self.near_error_threshold:raise ValueError('Major error threshold must exceed the near-miss threshold')
        return self


def root_for(project_path):
    manifest=Path(project_path).resolve();p=read_model(manifest,Project)
    from .projects import Recording
    if len(p.recording_manifests)!=1:raise ValueError('This refinement adapter currently supports one recording per project')
    recording=read_model(resolve_relative(manifest.parent,p.recording_manifests[0]),Recording)
    return recording_structure(manifest.parent,recording.recording_id).application_dir('skellyclicker')/'refinement-runs'


def folder(project_path,run_id):
    UUID(run_id);path=root_for(project_path)/run_id
    if not path.is_dir():raise ValueError('Refinement round not found')
    return path


@router.post('/runs',status_code=202)
def start(request:MineRequest):
    with guard:
        if busy():raise HTTPException(409,'Stop the active job and wait for its checkpoint before finding new examples')
        try:
            manifest=Path(request.project_path).resolve();p=read_model(manifest,Project)
            summary=json.loads((resolve_relative(manifest.parent,p.sample_result)/'summary.json').read_text())
            frames=[r['source_frame'] for r in summary['frames']]
            labels=PreviewLabels(project_path=request.project_path,start_frame=min(frames),end_frame=max(frames))
            bound=bind_inputs(labels)
            previous=folder_for(request.project_path,request.parent_run_id)
            dataset=json.loads((previous/'dataset.json').read_text())
            parent=bind_parent(request,{'project_uuid':p.uuid,'stl_sha256':bound.target.geometry.sha256,'stl_units':bound.target.authored_units,'keypoint_names':list(bound.authored['names']),'keypoint_definition_source_sha256':bound.authored['manifest']['keypoints']['sha256']})
            if dataset['manifest']['source_sha256']!=bound.recording.source.sha256:raise ValueError('Model and recording source differ')
            paths=recording_structure(bound.root,bound.recording.recording_id)
            from .recording_layout import verify_recording_inputs
            info=verify_recording_inputs(paths)
            if info['input_provenance']['source_sha256']!=bound.recording.source.sha256:raise ValueError('Synchronized videos differ from the current recording')
            timing=json.loads(paths.source_timing_path.read_text())
            videos={camera:str(resolve_relative(paths.videos_synchronized_dir,name)) for camera,name in info['videos'].items()}
            if not videos or any(not Path(v).is_file() for v in videos.values()):raise ValueError('Materialize synchronized recording videos before refinement')
            source_prepared=json.loads((previous/'prepared.json').read_text())
            reviewed=result_view(manifest);selection=selection_view(manifest)
        except (ValueError,OSError,KeyError,TypeError) as error:raise HTTPException(422,str(error)) from error
        job={}
        def observe(snapshot):
            job['status']={'state':snapshot['status'],**snapshot};atomic_json(job['work']/'status.json',snapshot)
        run=PipelineRun(GRAPH,labels={'mine_examples':'Analyze recording and propose additions'},on_snapshot=observe)
        work=root_for(request.project_path)/run.run_id;work.mkdir(parents=True)
        job.update(kind='refinement',manifest=manifest,root=manifest.parent,work=work,request=request.model_dump(),status={'state':'queued'},cancel=RunCancellation(run),run=run,process=None,started=time.monotonic())
        atomic_json(work/'request.json',request.model_dump())
        def mine_handler(_,ctx):
            cache=projection_source(bound,work,ctx);accepted={r['source_frame'] for r in bound.rows if r['accepted']};references={}
            with cache.open() as stream:
                for line in stream:
                    item=json.loads(line);projection=item['projection']
                    if item['source_frame'] in accepted and projection and projection.get('positive_depth') and projection.get('keypoints_xy') is not None:
                        references[f"{item['source_frame']}:{item['camera']}"]={'xy':projection['keypoints_xy']}
            shutil.copyfile(parent['source_path'],work/'model.pt')
            if file_digest(work/'model.pt')!=parent['sha256']:raise ValueError('Checkpoint changed during snapshot')
            cutoff=int(dataset['manifest']['validation_start_ns'])-round(dataset['manifest']['guard_seconds']*1_000_000_000)
            worker={**request.model_dump(),'checkpoint':str(work/'model.pt'),'checkpoint_sha256':parent['sha256'],'pose_config':source_prepared['pose'],'keypoint_count':len(bound.authored['names']),'videos':videos,'source_frames':timing['source_frame_indices'],'timestamps_ns':[str(t) for t in timing['timestamps_ns']],'training_cutoff_ns':str(cutoff),'references':references,'reviewed_keys':[f"{r['source_frame']}:{r['camera_id']}" for r in reviewed['images']] if reviewed else []}
            atomic_json(work/'worker-request.json',worker)
            atomic_json(work/'binding.json',{'pose_sha256':bound.pose_hash,'target_sha256':bound.target_hash,'selection_sha256':selection['sha256'],'label_manifest_sha256':reviewed['manifest_sha256'] if reviewed else None})
            ctx.progress(0,len(worker['source_frames'])*len(videos),'images','Scanning synchronized recording')
            run_worker('mine',job,ctx);ctx.check_cancelled();ctx.artifacts(writes=(work/'result.json',work/'predictions.jsonl'))
            return {}
        registry.add(run);jobs[run.run_id]=job
        thread=threading.Thread(target=lambda:run.execute({'mine_examples':mine_handler},resource_capacity={'compute':1}),name='skellyclicker-refinement',daemon=False)
        job['thread']=thread;thread.start();return {'run_id':run.run_id}


@router.get('/latest')
def latest(project_path:str):
    try:
        root=root_for(project_path);paths=sorted(root.glob('*/request.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        return inspect(paths[0].parent.name,project_path) if paths else None
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error


@router.get('/runs/{run_id}')
def inspect(run_id:str,project_path:str):
    try:
        work=folder(project_path,run_id);snapshot=jobs[run_id]['run'].snapshot() if run_id in jobs else json.loads((work/'status.json').read_text())
        if run_id not in jobs and snapshot['status'] in ('running','queued'):snapshot.update(status='failed',error='Analysis interrupted; saved artifacts remain. Start a new analysis to retry.')
        accepted=json.loads((work/'accepted.json').read_text()) if (work/'accepted.json').exists() else None
        if accepted:
            label_work=work.parent.parent/'working'/'labels'/accepted['run_id']
            status_path=label_work/'status.json'
            if status_path.exists():
                label_status=json.loads(status_path.read_text())
                if accepted['run_id'] not in jobs and label_status['status'] in ('running','queued'):label_status.update(status='failed',error='Label generation was interrupted. Inspect the retained dataset before retrying.')
                accepted={**accepted,'snapshot':label_status}
        return {'run_id':run_id,'snapshot':snapshot,'result':json.loads((work/'result.json').read_text()) if snapshot['status']=='complete' and (work/'result.json').exists() else None,'accepted':accepted}
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error


@router.get('/runs/{run_id}/image')
def image(run_id:str,project_path:str,key:str):
    try:
        work=folder(project_path,run_id);result=json.loads((work/'result.json').read_text());row=next(r for r in result['proposals'] if r['key']==key)
        return FileResponse(resolve_relative(work,row['preview']),media_type='image/png')
    except (ValueError,OSError,KeyError,StopIteration) as error:raise HTTPException(404,'Proposal image unavailable') from error


class Accept(Model):
    project_path:str
    image_keys:list[str]

@router.post('/runs/{run_id}/accept',status_code=202)
def accept(run_id:str,request:Accept):
    try:
        work=folder(request.project_path,run_id)
        if (work/'accepted.json').exists():return json.loads((work/'accepted.json').read_text())
        proposal=inspect(run_id,request.project_path)
        if not proposal['result']:raise ValueError('Wait for analysis to finish before accepting additions')
        allowed={r['key'] for r in proposal['result']['proposals']}
        if not request.image_keys or not set(request.image_keys)<=allowed or len(set(request.image_keys))!=len(request.image_keys):raise ValueError('Choose distinct images from this proposal')
        manifest=Path(request.project_path).resolve();binding=json.loads((work/'binding.json').read_text())
        selected=selection_view(manifest);current=result_view(manifest)
        if selected['sha256']!=binding['selection_sha256'] or (current['manifest_sha256'] if current else None)!=binding['label_manifest_sha256']:raise ValueError('The dataset changed during review. Analyze again before adding these proposals.')
        frames=[int(k.split(':')[0]) for k in request.image_keys]
        response=start_labels(GenerateLabels(project_path=request.project_path,start_frame=min(frames),end_frame=max(frames),image_keys=request.image_keys,expected_pose_manifest_sha256=binding['pose_sha256'],expected_target_manifest_sha256=binding['target_sha256']))
        atomic_json(work/'accepted.json',response);return response
    except HTTPException:raise
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error
