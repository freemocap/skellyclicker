"""The APP's training recipe uses the SDK's typed graph and shared task registry."""
from freemocap_sdk.pipeline import DataContract,DataGranularity,GraphPort,GraphNode,GraphConnection,PortReference,InputBindingRule,GraphDefinition,compile_graph

def port(name,kind):return GraphPort(name=name,contract=DataContract(kind=kind,data_granularity=DataGranularity.RECORDING,namespace='skellyclicker.training.v1'))
def edge(a,out,b,inp):return GraphConnection(source=PortReference(node=a,port=out),target=PortReference(node=b,port=inp),binding=InputBindingRule.SAME_KEY)
GRAPH=compile_graph(GraphDefinition(nodes=(
 GraphNode(id='freeze_inputs',operation='freeze_inputs',effects=('read_record','write_disk'),outputs=(port('dataset','approved_dataset'),)),
 GraphNode(id='prepare_trainer',operation='prepare_trainer',effects=('read_record','write_disk'),inputs=(port('dataset','approved_dataset'),),outputs=(port('prepared','dlc_project'),)),
 GraphNode(id='train_model',operation='train_model',effects=('read_record','write_disk'),inputs=(port('prepared','dlc_project'),),outputs=(port('trained','trained_model'),)),
 GraphNode(id='publish_run',operation='publish_run',effects=('read_record','write_disk'),inputs=(port('trained','trained_model'),),outputs=(port('result','training_result'),)),
),edges=(edge('freeze_inputs','dataset','prepare_trainer','dataset'),edge('prepare_trainer','prepared','train_model','prepared'),edge('train_model','trained','publish_run','trained'))))

import json,logging,os,subprocess,time
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import CancelledError
import pyarrow.parquet as pq
from freemocap_sdk.storage import atomic_json,file_digest,resolve_relative
from .training_inputs import freeze_training_inputs
from .label_inputs import checked

log=logging.getLogger('skellyclicker.training')

def consume_event(event,ctx,job):
    kind=event['kind']
    if kind=='metric':ctx.metric(event['id'],label=event['label'],step=event['step'],value=event['value'],unit=event['unit'],step_label='Epoch')
    elif kind=='preview':
        asset=resolve_relative(job['work'],event['path'])
        if not asset.is_file():raise ValueError('Worker preview was not published')
        url=f"/api/training/runs/{job['run'].run_id}/artifact?project_path={quote(str(job['manifest']),safe='')}&path={quote(event['path'],safe='')}"
        ctx.preview(event['id'],label=event['label'],image_url=url,step=event['step'],step_label='Epoch',checkpoint_id=event['checkpoint_id'])
    elif kind=='progress':ctx.progress(event['epoch'],job['request']['epochs'],'epochs',f"{event['detail']} · epoch {event['epoch']} / {job['request']['epochs']}")
    elif kind=='checkpoint':
        ctx.artifacts(writes=(resolve_relative(job['work'],event['path']),));log.info('Saved checkpoint at epoch %s',event['epoch'])
    elif kind=='error':job['worker_error']=event['message']


def run_worker(mode,job,ctx):
    work=job['work'];events=work/'events.jsonl';offset=events.stat().st_size if events.exists() else 0;partial=b''
    worker=Path(__file__).parent/'workers/train_dlc.py';cancel_at=None
    with (work/f'{mode}.log').open('w',encoding='utf-8') as output:
        process=subprocess.Popen([job['request']['python_path'],'-B',str(worker),mode,str(work)],stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        job['process']=process
        try:
            while True:
                if events.exists():
                    with events.open('rb') as stream:stream.seek(offset);data=stream.read();offset=stream.tell()
                    lines=(partial+data).split(b'\n');partial=lines.pop()
                    for line in lines:
                        if line:consume_event(json.loads(line),ctx,job)
                cancelled=job['cancel'].is_set();timeout=time.monotonic()-job['started']>job['request']['max_seconds']
                if cancelled or timeout:
                    (work/'STOP').touch(exist_ok=True)
                    if cancel_at is None:cancel_at=time.monotonic();log.info('Training stop requested; preserving completed checkpoints')
                    if process.poll() is None and time.monotonic()-cancel_at>15:process.terminate()
                code=process.poll()
                if code is not None:
                    # Drain final events written immediately before process exit.
                    if events.exists() and events.stat().st_size>offset:continue
                    if cancelled:raise CancelledError('Training cancelled; completed checkpoints retained')
                    if timeout:raise TimeoutError('Training exceeded its configured maximum duration; completed checkpoints retained')
                    if code:raise RuntimeError(job.get('worker_error',f'DLC {mode} failed with exit code {code}; see {mode}.log'))
                    break
                time.sleep(.1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            job['process']=None


def handlers(request,job):
    work=job['work']
    def freeze(inputs,ctx):
        ctx.check_cancelled();snapshot=freeze_training_inputs(request,check_cancelled=ctx.check_cancelled)
        dataset=resolve_relative(job['root'],snapshot['path']);job['dataset']=snapshot
        atomic_json(work/'dataset.json',snapshot)
        ctx.artifacts(reads=(job['manifest'],),writes=(dataset/'manifest.json',));ctx.progress(1,1,'datasets','Approved image selection frozen')
        return {'dataset':snapshot}
    def prepare(inputs,ctx):
        snapshot=inputs['dataset'];dataset=resolve_relative(job['root'],snapshot['path'])
        images=pq.read_table(dataset/'images.parquet').to_pylist();labels=pq.read_table(dataset/'labels.parquet').to_pylist();by_image={r['image_id']:[] for r in images}
        for r in labels:by_image[r['moment_id']+':'+r['camera_id']].append(r)
        for row in images:
            ordered=sorted(by_image[row['image_id']],key=lambda r:r['keypoint_index'])
            row['xy']=[[r['x_px'],r['y_px']] for r in ordered];row['valid']=[bool(r['projection_valid'] and r['in_bounds']) for r in ordered]
        worker_request={**request.model_dump(mode='json'),'dataset':str(dataset),'dataset_sha256':snapshot['manifest_sha256'],'images':images}
        atomic_json(work/'worker-request.json',worker_request);ctx.progress(0,1,'projects','Preparing official DLC project and verifying split')
        run_worker('prepare',job,ctx);ctx.check_cancelled();ctx.progress(1,1,'projects','DLC saved split verified')
        return {'prepared':str(work)}
    def train(inputs,ctx):
        ctx.check_cancelled();run_worker('train',job,ctx);ctx.check_cancelled()
        return {'trained':str(work)}
    def publish(inputs,ctx):
        ctx.check_cancelled();trained=json.loads((work/'trained.json').read_text());checkpoint=resolve_relative(work,trained['checkpoint'])
        if file_digest(checkpoint)!=trained['checkpoint_sha256']:raise ValueError('Completed checkpoint changed')
        metadata={'schema_version':1,'run_id':job['run'].run_id,'dataset':job['dataset'],'configuration':request.model_dump(mode='json'),
                  'trained':trained,'prepared':json.loads((work/'prepared.json').read_text()),'events_sha256':file_digest(work/'events.jsonl'),
                  'review_state':'approved','label_origin':'pose_projection'}
        atomic_json(work/'result.json',metadata);ctx.artifacts(writes=(work/'result.json',checkpoint));ctx.progress(1,1,'runs','Training result and provenance saved')
        return {'result':metadata}
    return {'freeze_inputs':freeze,'prepare_trainer':prepare,'train_model':train,'publish_run':publish}
