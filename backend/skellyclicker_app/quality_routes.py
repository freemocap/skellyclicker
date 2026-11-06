"""Transparent ranking of existing source-label diagnostics; no model inference."""
import hashlib,json,math
from collections import OrderedDict
from pathlib import Path
from typing import Literal
import pyarrow.parquet as pq
from fastapi import APIRouter,HTTPException
from pydantic import Field
from freemocap_sdk.storage import atomic_json,file_digest,project_lock,resolve_relative
from .projects import Model,Project,read_model,load_target
from .viewpoint_quality import mesh_frame,viewing_direction,spherical_bin,coverage_pool,select_viewpoints
from urllib.parse import urlencode
from fastapi.responses import FileResponse
from .label_routes import result_view,selection_view
from .label_inputs import checked
from .selection_storage import write_selection
from .job_lifecycle import guard,busy

router=APIRouter(prefix='/api/labels')
FACTORS=('iou','mask_fraction','depth_coverage','depth_agreement','in_bounds_fraction')
class QualityRequest(Model):
    project_path:str
    expected_label_manifest_sha256:str
    expected_selection_sha256:str|None
    selection_mode:Literal['quality_viewpoints','quality_only']='quality_viewpoints'
    azimuth_bins:int=Field(default=12,ge=4,le=36)
    z_bins:int=Field(default=6,ge=2,le=18)
    top_n:int=Field(default=100,ge=1,le=100000)
    spacing_seconds:float=Field(default=0,ge=0,le=3600)
    require_fit_passed:bool=True
    min_iou:float=Field(default=.72,ge=0,le=1)
    min_mask_fraction:float=Field(default=.8,ge=0,le=1)
    min_depth_coverage:float=Field(default=.5,ge=0,le=1)
    min_common_depth_px:int=Field(default=100,ge=0)
    max_depth_error_mm:float=Field(default=5,gt=0)
    min_in_bounds_fraction:float=Field(default=.9,ge=0,le=1)
    weights:dict[str,float]=Field(default_factory=lambda:dict.fromkeys(FACTORS,1.0))

_previews=OrderedDict()
def bound(request):
    manifest=Path(request.project_path).resolve();result=result_view(manifest);selection=selection_view(manifest)
    if not result or result['manifest_sha256']!=request.expected_label_manifest_sha256 or selection['sha256']!=request.expected_selection_sha256:raise HTTPException(409,'Dataset changed; preview the current selection again')
    project=read_model(manifest,Project)
    if project.sample_result!=result['manifest']['pose_result'] or not project.target_manifests or file_digest(resolve_relative(manifest.parent,project.target_manifests[0]))!=result['manifest']['target_manifest_sha256']:raise HTTPException(409,'Pose or target differs from these labels')
    pose=resolve_relative(manifest.parent,result['manifest']['pose_result'])
    if file_digest(pose/'manifest.json')!=result['manifest']['pose_manifest_sha256']:raise HTTPException(409,'Source pose identity changed; prepare matching labels before selecting')
    if project.active_review:
        review=json.loads((resolve_relative(manifest.parent,project.active_review)/'manifest.json').read_text(encoding='utf-8'))
        if review['label_manifest_sha256']!=result['manifest_sha256'] or review['label_result']!=result['path']:raise HTTPException(409,'Selection belongs to different labels')
    return manifest,project,result,selection

def finite(value,lo=0,hi=None):
    return isinstance(value,(float,int)) and not isinstance(value,bool) and math.isfinite(value) and value>=lo and (hi is None or value<=hi)

def rank_rows(images,candidates,labels,request):
    weights=request.weights
    if set(weights)!=set(FACTORS) or any(not finite(v) for v in weights.values()) or not sum(weights.values()):raise ValueError('Use nonnegative weights for all five factors with at least one positive weight')
    grouped={}
    for r in labels:
        key=(r['moment_id'],r['camera_id']);a=grouped.setdefault(key,[0,0]);a[0]+=1
        a[1]+=bool(r['projection_valid'] and r['in_bounds'] and finite(r['x_px']) and finite(r['y_px']))
    rows=[]
    for image in images:
        c=candidates.get(image['source_frame'],{});n,good=grouped.get((image['moment_id'],image['camera_id']),(0,0))
        factors={'iou':c.get(image['camera_id']+'_iou'),'mask_fraction':c.get(image['camera_id']+'_mask_fraction'),'depth_coverage':c.get('depth_coverage'),'common_depth_px':c.get('common_depth_px'),'depth_error_mm':c.get('median_abs_depth_mm'),'in_bounds_fraction':good/n if n else None}
        factors={k:(v if finite(v,hi=1 if k in ('iou','mask_fraction','depth_coverage','in_bounds_fraction') else None) else None) for k,v in factors.items()}
        normalized={k:factors.get(k) for k in FACTORS};normalized['depth_agreement']=math.exp(-factors['depth_error_mm']/5) if finite(factors['depth_error_mm']) else None
        missing=[k for k in FACTORS if weights[k]>0 and not finite(normalized[k],hi=1)]
        reasons=['Missing '+k for k in missing]
        if not good:reasons.append('No valid in-bounds labels')
        if request.require_fit_passed and not c.get('accepted',False):reasons.append('Source fit did not pass')
        thresholds=(('iou',request.min_iou),('mask_fraction',request.min_mask_fraction),('depth_coverage',request.min_depth_coverage),('common_depth_px',request.min_common_depth_px),('in_bounds_fraction',request.min_in_bounds_fraction))
        for key,minimum in thresholds:
            if minimum>0 and (not finite(factors[key]) or factors[key]<minimum):reasons.append(key+' below minimum or unknown')
        if not finite(factors['depth_error_mm']) or factors['depth_error_mm']>request.max_depth_error_mm:reasons.append('Depth error exceeds maximum or unknown')
        score=None if missing else 100*sum(weights[k]*normalized[k] for k in FACTORS if weights[k]>0)/sum(weights.values())
        rows.append({**{k:image[k] for k in ('image_id','source_frame','camera_id','timestamp_ns')},'score':score,'factors':factors,'fit_passed':bool(c.get('accepted',False)),'eligible':not reasons,'unknown':bool(missing),'reasons':reasons,'selected':True})
    rows.sort(key=lambda r:(r['score'] is None,-(r['score'] or 0),r['source_frame'],r['camera_id'],r['image_id']))
    chosen=[];timestamps={}
    for row in rows:
        if not row['eligible']:continue
        stamp=int(row['timestamp_ns']);previous=timestamps.setdefault(row['camera_id'],[])
        if any(abs(stamp-t)<request.spacing_seconds*1e9 for t in previous):continue
        chosen.append(row['image_id']);previous.append(stamp)
        if len(chosen)>=request.top_n:break
    return rows,chosen

@router.post('/quality/preview')
def quality_preview(request:QualityRequest):
    try:
        with guard:
            manifest,project,result,selection=bound(request)
            source=resolve_relative(manifest.parent,result['manifest']['pose_result']);meta=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
            if file_digest(source/'manifest.json')!=result['manifest']['pose_manifest_sha256']:raise ValueError('Source pose manifest changed')
            checked(source/'candidates.parquet',meta['files']['candidates.parquet'])
            candidates={r['source_frame']:r for r in pq.read_table(source/'candidates.parquet').to_pylist()}
            labels=pq.read_table(resolve_relative(manifest.parent,result['path'])/'labels.parquet').to_pylist()
            selected=set(selection['selected_image_ids']);images=[r for r in result['images'] if r['image_id'] in selected]
            rows,_=rank_rows(images,candidates,labels,request)
            target=load_target(manifest.parent,project.target_manifests[0]);stl=resolve_relative(manifest.parent,target.geometry.path)
            center,radius,scale=mesh_frame(stl,target.geometry.sha256,target.geometry.bytes,stl.stat().st_mtime_ns,target.authored_units)
            for row in rows:
                source_row=candidates.get(row['source_frame'],{});row['quality_eligible']=row['eligible']
                direction=viewing_direction(source_row.get('T_'+row['camera_id']+'_from_stl_m'),center) if source_row.get('accepted') or row['quality_eligible'] else None
                row['viewpoint']={'direction':direction,'bin':spherical_bin(direction,request.azimuth_bins,request.z_bins)} if direction is not None else None
                if request.selection_mode=='quality_viewpoints' and direction is None:
                    row['eligible']=False;row['reasons'].append('Missing or unreliable source viewpoint')
            ids=select_viewpoints(rows,request);chosen=set(ids)
            coverage={'azimuth_bins':request.azimuth_bins,'z_bins':request.z_bins,'cell_solid_angle_sr':4*math.pi/(request.azimuth_bins*request.z_bins),'center_stl_m':center,'radius_m':radius,'stl_scale_to_m':scale,'frame':'original_stl','stl_url':'/api/labels/quality/stl?'+urlencode({'project_path':str(manifest),'target_sha256':target.geometry.sha256}),
                'pools':{name:coverage_pool(items,request.azimuth_bins,request.z_bins) for name,items in [('current',rows),('eligible',[r for r in rows if r['quality_eligible']]),('proposed',[r for r in rows if r['image_id'] in chosen])]}}

            policy=request.model_dump(exclude={'project_path','expected_label_manifest_sha256','expected_selection_sha256'})
            provenance={'version':1,'formula':'100 * weighted_mean(iou, mask_fraction, depth_coverage, exp(-depth_error_mm/5), in_bounds_fraction)','scope':'current_members','source_pose_manifest_sha256':result['manifest']['pose_manifest_sha256'],'policy':policy,'label_manifest_sha256':result['manifest_sha256'],'selection_sha256':selection['sha256'],'image_ids':ids,'viewpoint_definition':{'frame':'original_stl','center_stl_m':center,'units':'m','binning':'uniform_z_and_azimuth','area_sr':coverage['cell_solid_angle_sr']}}
            token=hashlib.sha256(json.dumps(provenance,sort_keys=True).encode()).hexdigest();_previews[token]=(str(manifest),provenance)
            _previews.move_to_end(token)
            while len(_previews)>128:_previews.popitem(last=False)
            return {'preview_id':token,**provenance,'rows':rows,'coverage':coverage,'counts':{'current':len(images),'eligible':sum(r['eligible'] for r in rows),'unknown':sum(r['unknown'] for r in rows),'viewpoint_unknown':sum(r['viewpoint'] is None for r in rows),'chosen':len(ids),'excluded':len(result['images'])-len(images)}}
    except HTTPException:raise
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error

class BulkSelection(Model):
    project_path:str
    expected_label_manifest_sha256:str
    expected_selection_sha256:str|None
    operation:Literal['keep','remove','restore']
    image_ids:list[str]
    preview_id:str|None=None

@router.post('/selection/bulk')
def bulk_selection(request:BulkSelection):
    try:
        with guard:
            if busy(ignore_training=True):raise HTTPException(409,'A preparation or label run is active')
            manifest=Path(request.project_path).resolve()
            with project_lock(manifest.parent):
                manifest,project,result,current=bound(request)
                ids=set(request.image_ids);all_ids={r['image_id'] for r in result['images']};before=set(current['selected_image_ids'])
                if len(ids)!=len(request.image_ids) or not ids<=all_ids:raise ValueError('Choose distinct generated image IDs')
                if request.operation!='restore' and not ids<=before:raise HTTPException(409,'Selection contains previously excluded images; preview again')
                provenance=None
                if request.preview_id:
                    entry=_previews.get(request.preview_id)
                    if not entry or entry[0]!=str(manifest):raise HTTPException(409,'Ranking preview expired; preview again')
                    provenance=entry[1]
                    if request.operation!='keep' or ids!=set(provenance['image_ids']) or provenance['selection_sha256']!=current['sha256'] or provenance['label_manifest_sha256']!=result['manifest_sha256']:raise HTTPException(409,'Ranking preview differs from this selection')
                after=ids if request.operation=='keep' else before-ids if request.operation=='remove' else before|ids
                receipt={'before_count':len(before),'after_count':len(after),'removed_count':len(before-after),'added_count':len(after-before),'added_image_ids':sorted(after-before),'removed_image_ids':sorted(before-after),'ranking':provenance}
                if after==before:return {**current,'receipt':receipt}
                rows=[r for r in result['images'] if r['image_id'] in after]
                review=write_selection(manifest.parent,result['manifest']['recording_id'],result['path'],result['manifest_sha256'],rows,current['sha256'],reason='bulk_'+request.operation,membership_change=receipt)
                project.active_review=review;atomic_json(manifest,project.model_dump(mode='json'))
                return {**selection_view(manifest),'receipt':receipt}
    except HTTPException:raise
    except (ValueError,OSError,KeyError) as error:raise HTTPException(422,str(error)) from error


@router.get('/quality/stl')
def quality_stl(project_path:str,target_sha256:str):
    try:
        manifest=Path(project_path).resolve();project=read_model(manifest,Project);target=load_target(manifest.parent,project.target_manifests[0])
        if target.geometry.sha256!=target_sha256:raise HTTPException(409,'Target changed; preview again')
        path=checked(resolve_relative(manifest.parent,target.geometry.path),target.geometry.model_dump())
        return FileResponse(path,media_type='model/stl',headers={'Cache-Control':'private, max-age=3600'})
    except HTTPException:raise
    except (ValueError,OSError,KeyError,IndexError) as error:raise HTTPException(422,str(error)) from error
