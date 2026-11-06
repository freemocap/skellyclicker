"""Label execution endpoints; lifecycle and status transport come from the SDK."""
import json
from pathlib import Path
import threading
from typing import Annotated
from fastapi import APIRouter,HTTPException,Query
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
    by_moment={row['moment_id']:row for row in moments}
    images=[{**row,**{k:by_moment[row['moment_id']][k] for k in ('source_frame','timestamp_ns','playback_frame')},
             'image_id':row['moment_id']+':'+row['camera_id']} for row in pq.read_table(folder/'images.parquet').to_pylist()]
    return {'images':images,'path':selected,'manifest_sha256':file_digest(folder/'manifest.json'),'manifest':metadata,'moments':moments,
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

# Human inclusion is review and approval; generated initial inclusion is a proposal.
from pydantic import Field
from uuid import uuid4
import pyarrow as pa
from freemocap_sdk.storage import project_lock,publish_directory
from .projects import Model
from .selection_storage import write_selection

class SelectMoment(Model):
    project_path:str
    expected_label_manifest_sha256:str
    expected_selection_sha256:str|None=None
    moment_id:str|None=None
    source_frame:int|None=Field(default=None,ge=0)
    timestamp_ns:str|None=Field(default=None,pattern='^[0-9]+$')
    selected:bool
    camera_id:str|None=None
    include_all:bool=False


def selection_view(manifest):
    project=read_model(manifest,Project)
    if not project.active_review:return {'sha256':None,'selected_moment_ids':[],'selected_image_ids':[],'review_state':'unreviewed'}
    folder=resolve_relative(manifest.parent,project.active_review)
    metadata=json.loads((folder/'manifest.json').read_text())
    checked(folder/'selection.parquet',metadata['files']['selection.parquet'])
    rows=pq.read_table(folder/'selection.parquet').to_pylist()
    if metadata.get('schema_version',1)==1:
        result=result_view(manifest)
        if not result or result['manifest_sha256']!=metadata['label_manifest_sha256']:raise ValueError('Selection belongs to another label result')
        ids={r['moment_id'] for r in rows};rows=[r for r in result['images'] if r['moment_id'] in ids]
    return {'sha256':file_digest(folder/'manifest.json'),'selected_moment_ids':list(dict.fromkeys(r['moment_id'] for r in rows)),
            'selected_image_ids':[r['image_id'] for r in rows],
            'review_state':'proposed' if metadata.get('initialization')=='generated_candidates_included' else 'approved'}


@router.get('/selection')
def selected_moments(project_path:str):
    try:return selection_view(Path(project_path).resolve())
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error


@router.post('/selection')
def save_selection(request:SelectMoment):
    manifest=Path(request.project_path).resolve()
    try:
        with guard:
            if busy(ignore_training=True):raise HTTPException(409,'A preparation or label run is active')
            with project_lock(manifest.parent):
                result=result_view(manifest)
                if not result or result['manifest_sha256']!=request.expected_label_manifest_sha256:raise HTTPException(409,'Generated labels changed; reload before selecting')
                project=read_model(manifest,Project)
                if project.sample_result!=result['manifest']['pose_result'] or not project.target_manifests or file_digest(resolve_relative(manifest.parent,project.target_manifests[0]))!=result['manifest']['target_manifest_sha256']:
                    raise HTTPException(409,'Current pose or target selection differs from these labels')
                current=selection_view(manifest)
                if current['sha256']!=request.expected_selection_sha256:raise HTTPException(409,'Selection changed; reload before selecting')
                if request.include_all:
                    if not request.selected:raise HTTPException(422,'Include all requires selected=true')
                    chosen=result['images']
                else:
                    moment=next((row for row in result['moments'] if row['moment_id']==request.moment_id),None)
                    if not moment or moment['source_frame']!=request.source_frame or moment['timestamp_ns']!=request.timestamp_ns:raise HTTPException(422,'Presented source identity does not match a generated moment')
                    chosen=[r for r in result['images'] if r['moment_id']==request.moment_id and (request.camera_id is None or r['camera_id']==request.camera_id)]
                    if not chosen:raise HTTPException(422,'No generated image for this camera and moment')
                selected=set(current['selected_image_ids']);ids={r['image_id'] for r in chosen}
                if request.selected:selected.update(ids)
                else:selected.difference_update(ids)
                rows=[r for r in result['images'] if r['image_id'] in selected]
                review=write_selection(manifest.parent,result['manifest']['recording_id'],result['path'],result['manifest_sha256'],rows,current['sha256'],reason='include_all' if request.include_all else 'manual')
                project=read_model(manifest,Project);project.active_review=review
                atomic_json(manifest,project.model_dump(mode='json'))
                return selection_view(manifest)
    except HTTPException:raise
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error


from functools import lru_cache
from io import BytesIO
from fastapi.responses import Response,FileResponse
from PIL import Image,ImageDraw
from .target_crops import target_crop_metadata,projection_offset

@lru_cache(maxsize=128)
def image_thumbnail(path,sha256,size,modified_ns,bounds,points,projection_path,offset,projection_digest,annotated=True,max_size=320):
    checked(path,{'sha256':sha256,'bytes':size})
    with Image.open(path) as original:
        image=original.convert('RGB')
        if annotated:
            draw=ImageDraw.Draw(image)
            with projection_path.open('rb') as stream:
                stream.seek(offset);projection=json.loads(stream.readline())['projection']
            for segment in (projection or {}).get('mesh_wireframe_segments_xy',[]):
                draw.line([tuple(point) for point in segment],fill='#37eaff',width=1)
            for x,y,visible in points:
                draw.ellipse((x-2,y-2,x+2,y+2),fill='#ff45e6' if visible else None,outline='#ff45e6',width=1)
        if bounds is not None:
            x,y,width,height=bounds
            image=image.crop((int(x),int(y),int(x+width+.999),int(y+height+.999)))
        if max_size:image.thumbnail((max_size,max_size))
        output=BytesIO();image.save(output,format='PNG',compress_level=3)
    return output.getvalue()

def thumbnail_fingerprint(manifest,project):
    # Only immutable label/geometry inputs affect thumbnails; membership does not.
    root=manifest.parent;label=resolve_relative(root,project.label_result);pose=resolve_relative(root,project.sample_result);playback=resolve_relative(root,project.playback_result)
    files=[label/'manifest.json',label/'images.parquet',label/'moments.parquet',label/'labels.parquet',pose/'manifest.json',pose/'timing.parquet',pose/'calibration.json',playback/'inventory.json',playback/'provenance.json',playback/'playback.json',playback/'outline-projections.jsonl']
    from .projects import load_target
    target=load_target(root,project.target_manifests[0]);target_path=resolve_relative(root,project.target_manifests[0]);files.extend(p for p in target_path.parent.rglob('*') if p.is_file());files.append(resolve_relative(root,target.geometry.path))
    return tuple((str(p),p.stat().st_size,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for p in sorted(set(files)))

_thumbnail_context_lock=threading.Lock()
@lru_cache(maxsize=2)
def thumbnail_context(manifest,label_path,pose_path,playback_path,fingerprint):
    project=read_model(manifest,Project);result=result_view(manifest,label_path)
    if project.sample_result!=pose_path or project.playback_result!=playback_path or result['manifest']['pose_result']!=pose_path:raise ValueError('Playback differs from these labels')
    crops=target_crop_metadata(manifest.parent,project,result['playback_id']);points={}
    for r in pq.read_table(resolve_relative(manifest.parent,result['path'])/'labels.parquet').to_pylist():
        if r['projection_valid']:points.setdefault((r['moment_id'],r['camera_id']),[]).append((r['x_px'],r['y_px'],bool(r['self_visible'])))
    return result['manifest_sha256'],{r['image_id']:r for r in result['images']},{k:tuple(v) for k,v in points.items()},crops

def image_response(project_path,label_manifest_sha256,image_id,*,crop,annotated,max_size,full_resolution=False):
    try:
        manifest=Path(project_path).resolve();project=read_model(manifest,Project)
        if not project.label_result or not project.playback_result:raise HTTPException(404,'No generated labels')
        fingerprint=thumbnail_fingerprint(manifest,project)
        with _thumbnail_context_lock:
            digest,images,points,crops=thumbnail_context(manifest,project.label_result,project.sample_result,project.playback_result,fingerprint)
        if digest!=label_manifest_sha256:raise HTTPException(409,'Generated labels changed')
        row=images.get(image_id)
        if not row:raise HTTPException(404,'Unknown generated image')
        path=resolve_relative(manifest.parent,row['path'])
        headers={'Cache-Control':'private, max-age=3600','X-Image-Id':image_id,'X-Label-Manifest':digest,'X-Annotations':'true' if annotated else 'false'}
        if full_resolution and not annotated:
            checked(path,{'sha256':row['sha256'],'bytes':row['bytes']})
            return FileResponse(path,media_type='image/png',headers=headers)
        bounds=None
        if crop:
            box=crops['cameras'].get(row['camera_id'],{}).get(str(row['source_frame']))
            if not box:return Response(status_code=204,headers={'X-Target-Crop':'unavailable',**headers})
            bounds=tuple(box[k] for k in ('x','y','width','height'))
        projection_path,offset,projection_digest=projection_offset(manifest.parent,project,row['camera_id'],row['source_frame'],crops['width'],crops['height'])
        data=image_thumbnail(path,row['sha256'],row['bytes'],path.stat().st_mtime_ns,bounds,points.get((row['moment_id'],row['camera_id']),()),projection_path,offset,projection_digest,annotated,max_size)
        return Response(data,media_type='image/png',headers=headers)
    except HTTPException:raise
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error

@router.get('/thumbnail')
def thumbnail(project_path:str,label_manifest_sha256:str,image_id:str,crop:bool=True,annotated:bool=True,max_size:Annotated[int,Query(ge=64,le=1024)]=320):
    return image_response(project_path,label_manifest_sha256,image_id,crop=crop,annotated=annotated,max_size=max_size)

@router.get('/image')
def full_image(project_path:str,label_manifest_sha256:str,image_id:str,annotated:bool=True):
    return image_response(project_path,label_manifest_sha256,image_id,crop=False,annotated=annotated,max_size=0,full_resolution=True)
