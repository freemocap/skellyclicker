"""Prepared-data label recipe; SDK schedules operations and publishes progress."""
import json
import hashlib
import marshal
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from freemocap_sdk.pipeline import DataContract,DataGranularity,GraphPort,GraphNode,GraphConnection,PortReference,InputBindingRule,GraphDefinition,compile_graph
from freemocap_sdk.storage import atomic_json,file_digest,inventory,project_lock,publish_directory,resolve_relative
from .selection_storage import write_selection
from .projects import read_model,Project,recording_structure
from .label_inputs import bind_inputs,checked,StaleInputs
from .authored_geometry import project_authored_geometry


def port(name,kind):return GraphPort(name=name,contract=DataContract(kind=kind,data_granularity=DataGranularity.RECORDING,namespace='skellyclicker.labels.v1'))
def edge(a,out,b,inp):return GraphConnection(source=PortReference(node=a,port=out),target=PortReference(node=b,port=inp),binding=InputBindingRule.SAME_KEY)
GRAPH=compile_graph(GraphDefinition(nodes=(
    GraphNode(id='bind_inputs',operation='bind_inputs',effects=('read_record',),outputs=(port('bound','bound_inputs'),)),
    GraphNode(id='choose_moments',operation='choose_moments',effects=('read_record',),inputs=(port('bound','bound_inputs'),),outputs=(port('moments','chosen_moments'),)),
    GraphNode(id='project_labels',operation='project_labels',effects=('read_record','write_disk'),inputs=(port('bound','bound_inputs'),port('moments','chosen_moments')),outputs=(port('staged','staged_labels'),)),
    GraphNode(id='publish_candidates',operation='publish_candidates',effects=('read_record','write_disk'),inputs=(port('bound','bound_inputs'),port('staged','staged_labels')),outputs=(port('result','published_labels'),)),
),edges=(edge('bind_inputs','bound','choose_moments','bound'),edge('bind_inputs','bound','project_labels','bound'),edge('choose_moments','moments','project_labels','moments'),edge('bind_inputs','bound','publish_candidates','bound'),edge('project_labels','staged','publish_candidates','staged'))))


def projection_source(bound,work,ctx):
    if bound.project.playback_result:
        folder=resolve_relative(bound.root,bound.project.playback_result)
        identities=json.loads((folder/'inventory.json').read_text(encoding='utf-8'))
        checked(folder/'provenance.json',identities['provenance.json'])
        provenance=json.loads((folder/'provenance.json').read_text(encoding='utf-8'))
        definition=provenance.get('authored_geometry',{}).get('definition',{})
        current=bound.authored['manifest']
        matches=(provenance['source_manifest_sha256']==bound.pose_hash and provenance['source_geometry_sha256']==bound.target.geometry.sha256
                 and all(definition.get(k,{}).get('sha256')==current[k]['sha256'] for k in ('keypoints','outline'))
                 and definition.get('origin_mm')==current['origin_mm'])
        if matches:
            cache=checked(folder/'outline-projections.jsonl',identities['outline-projections.jsonl'])
            ctx.artifacts(reads=(cache,folder/'provenance.json'))
            return cache
    return project_authored_geometry(bound.authored,bound.selected,bound.authority['descriptor']['calibration'],work,ctx.check_cancelled)


def handlers(request,work,run_id):
    def bind(_,ctx):
        ctx.check_cancelled();bound=bind_inputs(request,verify_source=True)
        ctx.artifacts(reads=(bound.result/'manifest.json',bound.target_path))
        ctx.progress(1,1,'input bundles','Verified prepared input identities')
        return {'bound':bound}
    def choose(inputs,ctx):
        bound=inputs['bound'];ctx.check_cancelled()
        ctx.progress(len(bound.selected),len(bound.selected),'paired moments','Range, filter, stride and cap applied')
        return {'moments':bound.selected}
    def project(inputs,ctx):
        bound=inputs['bound'];moments=inputs['moments'];output=work/'output';output.mkdir()
        cache=projection_source(bound,work,ctx);wanted={r['source_frame']:r for r in moments};projections={}
        with cache.open(encoding='utf-8') as stream:
            for line in stream:
                ctx.check_cancelled();item=json.loads(line);key=(item['source_frame'],item['camera'])
                if key[0] in wanted and key[1] in ('left','right'):
                    if key in projections:raise ValueError('Duplicate projection identity')
                    value=item['projection'];projections[key]={k:value.get(k) for k in ('keypoints_xy','visibility','positive_depth')} if value else None
        names=list(bound.authored['names']);n=len(names);cal=bound.authority['descriptor']['calibration']
        labels={k:[] for k in ['moment_id','camera_id','keypoint_index','x_px','y_px','projection_valid','in_bounds','self_visible','external_occlusion','invalid_reason']};images=[];moment_rows=[]
        for i,row in enumerate(moments):
            ctx.check_cancelled();frame=row['source_frame'];mid=f'{bound.recording.uuid}:{frame}'
            moment_rows.append({'moment_id':mid,'source_frame':frame,'timestamp_ns':row['timestamp_ns'],'fit_passed':bool(row['accepted']),'fit_status':row['status']})
            for camera in ('left','right'):
                if request.image_keys is not None and f'{frame}:{camera}' not in request.image_keys:continue
                projection=projections.get((frame,camera));xy=np.full((n,2),np.nan)
                if projection and projection['keypoints_xy'] is not None:
                    xy=np.asarray(projection['keypoints_xy'],dtype=float)
                    if xy.shape!=(n,2):raise ValueError('Projection keypoint order/count differs from target')
                valid=np.isfinite(xy).all(axis=1)&bool(projection and projection['positive_depth'])
                inside=valid&(xy[:,0]>=0)&(xy[:,0]<cal['image_width'])&(xy[:,1]>=0)&(xy[:,1]<cal['image_height'])
                visibility=projection['visibility'] if projection else None
                if visibility is not None and (len(visibility)!=n or any(type(v) is not bool for v in visibility)):raise ValueError('Invalid self-visibility vector')
                labels['moment_id'].extend([mid]*n);labels['camera_id'].extend([camera]*n);labels['keypoint_index'].extend(range(n))
                labels['x_px'].extend([float(x) if ok else None for x,ok in zip(xy[:,0],valid)]);labels['y_px'].extend([float(y) if ok else None for y,ok in zip(xy[:,1],valid)])
                labels['projection_valid'].extend(valid.tolist());labels['in_bounds'].extend(inside.tolist())
                labels['self_visible'].extend([visibility[j] if visibility is not None and valid[j] else None for j in range(n)])
                labels['external_occlusion'].extend(['unknown']*n);labels['invalid_reason'].extend([None if ok else 'missing_or_invalid_projection' for ok in valid])
                relative=f'frames/{frame:06d}-{camera}.png';identity=bound.authority['files'][relative];image=checked(resolve_relative(bound.result,relative),identity)
                images.append({'moment_id':mid,'camera_id':camera,'path':image.relative_to(bound.root).as_posix(),'sha256':identity['sha256'],'bytes':identity['bytes'],'width':cal['image_width'],'height':cal['image_height']})
            ctx.progress(i+1,len(moments),'paired moments',f'Projected {i+1} of {len(moments)} stereo moments')
        label_schema=pa.schema([('moment_id',pa.string()),('camera_id',pa.string()),('keypoint_index',pa.int32()),('x_px',pa.float64()),('y_px',pa.float64()),('projection_valid',pa.bool_()),('in_bounds',pa.bool_()),('self_visible',pa.bool_()),('external_occlusion',pa.string()),('invalid_reason',pa.string())])
        tables={'moments':pa.Table.from_pylist(moment_rows),'labels':pa.table(labels,schema=label_schema),'images':pa.Table.from_pylist(images)}
        for name,table in tables.items():
            table=table.replace_schema_metadata({b'skellyclicker.labels':json.dumps({'schema_version':1,'kind':name,'review_state':'unreviewed','keypoint_names':names,'timestamp_unit':'ns','pixel_convention':'opencv_integer_pixel_centres'}).encode()})
            pq.write_table(table,output/f'{name}.parquet')
        software={}
        for package in ('skellyclicker-app','freemocap-sdk-server','skellyforge','pyarrow','numpy'):
            try:software[package]=version(package)
            except PackageNotFoundError:software[package]=None
        manifest={'schema_version':1,'run_id':run_id,'project_uuid':bound.project.uuid,'recording_uuid':bound.recording.uuid,
            'recording_id':bound.recording.recording_id,'pose_result':bound.project.sample_result,'pose_manifest_sha256':bound.pose_hash,
            'target_manifest':bound.project.target_manifests[0],'target_manifest_sha256':bound.target_hash,
            'source_sha256':bound.recording.source.sha256,'stl_sha256':bound.target.geometry.sha256,'stl_units':bound.target.authored_units,
            'keypoint_definition_sha256':bound.authored['manifest']['keypoints']['sha256'],'keypoint_names':names,
            'calibration_sha256':bound.authority['files']['calibration.json']['sha256'],'projection_sha256':file_digest(cache),
            'software_versions':software,'recipe_bytecode_sha256':hashlib.sha256(marshal.dumps(handlers.__code__)).hexdigest(),
            'configuration':request.model_dump(mode='json'),'review_state':'unreviewed','label_origin':'pose_projection',
            'moment_count':len(moments),'image_count':len(images),'label_count':len(labels['moment_id']),
            'files':{key:value.model_dump() for key,value in inventory(output).items()}}
        atomic_json(output/'manifest.json',manifest);ctx.artifacts(writes=tuple(output.iterdir()))
        return {'staged':output}
    def publish(inputs,ctx):
        bound=inputs['bound'];output=inputs['staged'];ctx.check_cancelled()
        relative=(recording_structure(bound.root,bound.recording.recording_id).application_dir('skellyclicker')/'labels'/run_id/'r001').relative_to(bound.root).as_posix()
        destination=resolve_relative(bound.root,relative);destination.parent.mkdir(parents=True,exist_ok=True)
        with project_lock(bound.root):
            current=bind_inputs(request)
            if current.project.sample_result!=bound.project.sample_result or current.project.target_manifests!=bound.project.target_manifests:raise StaleInputs('Selected inputs changed during generation')
            for name,identity in json.loads((output/'manifest.json').read_text())['files'].items():checked(output/name,identity)
            # Accumulate candidates without resetting earlier human removals.
            # Immutable old label bundles remain independently inspectable.
            from .label_routes import result_view,selection_view
            previous=result_view(bound.manifest);previous_selection=selection_view(bound.manifest)
            if request.expected_selection_sha256 is not None and previous_selection['sha256']!=request.expected_selection_sha256:raise StaleInputs('Dataset membership changed while adding images; analyze again')
            if request.expected_label_manifest_sha256 is not None and (previous['manifest_sha256'] if previous else None)!=request.expected_label_manifest_sha256:raise StaleInputs('Labels changed while adding images; analyze again')
            old_ids=set();kept_ids=set(previous_selection['selected_image_ids'])
            if previous:
                metadata=json.loads((output/'manifest.json').read_text())
                for key in ('pose_manifest_sha256','target_manifest_sha256','keypoint_definition_sha256','calibration_sha256','source_sha256'):
                    if previous['manifest'][key]!=metadata[key]:raise ValueError('Existing reviewed data uses different prepared inputs; merging those revisions is not supported yet. Existing dataset was preserved.')
                old_folder=resolve_relative(bound.root,previous['path'])
                old_ids={r['image_id'] for r in previous['images']}
                for name,keys in [('moments',('moment_id',)),('images',('moment_id','camera_id')),('labels',('moment_id','camera_id','keypoint_index'))]:
                    old=pq.read_table(old_folder/(name+'.parquet'));new=pq.read_table(output/(name+'.parquet'))
                    rows={tuple(r[k] for k in keys):r for r in new.to_pylist()}
                    rows.update({tuple(r[k] for k in keys):r for r in old.to_pylist()})
                    pq.write_table(pa.Table.from_pylist(list(rows.values()),schema=new.schema),output/(name+'.parquet'))
                    metadata[{'moments':'moment_count','images':'image_count','labels':'label_count'}[name]]=len(rows)
                metadata['previous_label_result']=previous['path'];metadata['previous_label_manifest_sha256']=previous['manifest_sha256']
                metadata['files']={name:value.model_dump() for name,value in inventory(output).items() if name!='manifest.json'}
                atomic_json(output/'manifest.json',metadata)
            ctx.check_cancelled()
            publish_directory(staging=output,destination=destination)
            moments={row['moment_id']:row for row in pq.read_table(destination/'moments.parquet').to_pylist()}
            all_images=[{**row,**moments[row['moment_id']],'image_id':row['moment_id']+':'+row['camera_id']} for row in pq.read_table(destination/'images.parquet').to_pylist()]
            included=[r for r in all_images if r['image_id'] not in old_ids or r['image_id'] in kept_ids]
            after_ids={r['image_id'] for r in included}
            change={'before_count':len(kept_ids),'added_count':len(after_ids-kept_ids),'after_count':len(after_ids),'added_image_ids':sorted(after_ids-kept_ids)}
            review=write_selection(bound.root,bound.recording.recording_id,relative,file_digest(destination/'manifest.json'),included,previous_selection['sha256'],reason='generated_candidates_included',membership_change=change)
            selected=read_model(bound.manifest,Project);selected.label_result=relative;selected.active_review=review
            atomic_json(bound.manifest,selected.model_dump(mode='json'))
        # Publication is committed. Do not convert successful outputs into cancellation here.
        return {'result':{'path':relative,'manifest_sha256':file_digest(destination/'manifest.json'),'review_state':'unreviewed'}}
    return {'bind_inputs':bind,'choose_moments':choose,'project_labels':project,'publish_candidates':publish}
