"""Isolated DLC adapter. Official APIs/logger registry own optimization [@dlcTraining302]."""
import argparse,hashlib,json,math,os,sys,time,traceback
from pathlib import Path
os.environ.setdefault('DLClight','True');os.environ.setdefault('MPLBACKEND','Agg')
os.environ.setdefault('HF_HUB_OFFLINE','1')

class RequestedStop(Exception):pass

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def atomic(path,value):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,allow_nan=False),encoding='utf-8');os.replace(temp,path)

def emit(kind,**data):
    with (WORK/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'kind':kind,'time':time.time(),**data},allow_nan=False)+'\n')

def check_stop():
    if (WORK/'STOP').exists():raise RequestedStop()

def prepare(request):
    import numpy as np,pandas as pd,deeplabcut
    from deeplabcut.utils import auxiliaryfunctions as af
    from deeplabcut.core.engine import Engine
    from deeplabcut.core.config.utils import read_config_as_dict,write_config
    from deeplabcut.pose_estimation_pytorch.data.dlcloader import DLCLoader
    from copy import deepcopy
    from importlib.metadata import version
    if version('deeplabcut')!='3.0.2':raise ValueError('This adapter requires verified DeepLabCut 3.0.2')
    dataset=Path(request['dataset']);manifest=json.loads((dataset/'manifest.json').read_text())
    if digest(dataset/'manifest.json')!=request['dataset_sha256']:raise ValueError('Dataset manifest changed')
    for name,identity in manifest['files'].items():
        check_stop()
        if digest(dataset/name)!=identity['sha256']:raise ValueError('Dataset artifact changed: '+name)
    rows=sorted((r for r in request['images'] if r['split']!='guard'),key=lambda r:Path(r['path']).name)
    project=WORK/'dlc-project';folder=project/'labeled-data/geometry';folder.mkdir(parents=True)
    import shutil
    names=[];xy=[]
    for row in rows:
        check_stop();name=Path(row['path']).name;names.append(name);shutil.copyfile(dataset/row['path'],folder/name)
        points=np.asarray(row['xy'],dtype=float);valid=np.asarray(row['valid'],dtype=bool)
        # DLC accepts strict interior coordinates; preserve all original rows in the dataset.
        valid&=(points[:,0]>0)&(points[:,0]<row['width'])&(points[:,1]>0)&(points[:,1]<row['height'])
        points[~valid]=np.nan
        if not valid.any():raise ValueError('Included image has no trainable projected points: '+row['image_id'])
        xy.append(points)
    xy=np.asarray(xy);scorer='geometry'
    columns=pd.MultiIndex.from_product([[scorer],manifest['keypoint_names'],['x','y']],names=['scorer','bodyparts','coords'])
    table=pd.DataFrame(xy.reshape(len(rows),-1),index=pd.MultiIndex.from_tuples([('labeled-data','geometry',n) for n in names]),columns=columns)
    table.to_hdf(folder/f'CollectedData_{scorer}.h5',key='df_with_missing',mode='w')
    train=[i for i,r in enumerate(rows) if r['split']=='training'];test=[i for i,r in enumerate(rows) if r['split']=='validation']
    width,height=rows[0]['width'],rows[0]['height']
    if any((r['width'],r['height'])!=(width,height) for r in rows):raise ValueError('This adapter needs a consistent camera image size')
    config,_=af.create_config_template()
    config.update(Task='stl_tracking',scorer=scorer,date='Nov05',project_path=str(project.resolve()),video_sets={str(project/'videos/geometry.mp4'):{'crop':f'0, {width}, 0, {height}'}},bodyparts=manifest['keypoint_names'],skeleton=[],multianimalproject=False,default_net_type='resnet_50',default_augmenter='default',TrainingFraction=[round(len(train)/len(rows),2)],iteration=0,snapshotindex=-1,cropping=False,start=0,stop=1,numframes2pick=len(rows),x1=0,x2=width,y1=0,y2=height,batch_size=request['batch_size'],engine='pytorch')
    af.write_config(project/'config.yaml',config)
    deeplabcut.create_training_dataset(project/'config.yaml',Shuffles=[1],trainIndices=[train],testIndices=[test],net_type='resnet_50',engine=Engine.PYTORCH,userfeedback=False)
    posepath=next(project.glob('dlc-models-pytorch/**/train/pytorch_config.yaml'));pose=read_config_as_dict(posepath)
    for key in ('resize','longest_max_size','hflip','affine','random_bbox_transform','crop_sampling','top_down_crop'):pose['data']['inference'][key]=None
    pose['data']['train']=deepcopy(pose['data']['inference']);pose['data']['train'].update(hflip=False,motion_blur=True,gaussian_noise=12.75)
    pose['train_settings'].update(batch_size=request['batch_size'],dataloader_workers=0,seed=request['seed'],epochs=request['epochs'],display_iters=5)
    pose['runner']['snapshots'].update(save_epochs=request['save_every'],max_snapshots=5,save_optimizer_state=True)
    pose['runner']['eval_interval']=request['save_every'];pose['logger']=None
    write_config(posepath,pose)
    import cv2
    from deeplabcut.pose_estimation_pytorch.data.transforms import build_transforms
    sample=cv2.cvtColor(cv2.imread(str(folder/names[0])),cv2.COLOR_BGR2RGB)
    corners=np.array([[0,0],[width-1,0],[0,height-1],[width-1,height-1]],dtype=float)
    probe=build_transforms(pose['data']['train'])(image=sample,keypoints=corners.tolist(),class_labels=list(range(4)),bboxes=[],bbox_labels=[])
    if probe['image'].shape[:2]!=(height,width):raise ValueError('Training transform changes native image size')
    np.testing.assert_allclose(np.array(probe['keypoints'])[:,:2],corners,atol=.001)
    saved=DLCLoader.load_split(af.read_config(project/'config.yaml'),shuffle=1)
    merged,=(project/'training-datasets').rglob(f'CollectedData_{scorer}.h5');index=pd.read_hdf(merged).index
    for key,indices in [('train',train),('test',test)]:
        if {index[i][-1] for i in saved[key]}!={names[i] for i in indices}:raise ValueError('DLC saved split differs from frozen input')
    DLCLoader(project/'config.yaml',shuffle=1)  # Validate the saved typed model config before GPU work.
    versions={p:version(p) for p in ('deeplabcut','torch','torchvision','numpy','pandas')}
    atomic(WORK/'prepared.json',{'config':str(project/'config.yaml'),'pose':str(posepath),'dataset_sha256':request['dataset_sha256'],'train_count':len(train),'validation_count':len(test),'split_verified':True,'software':versions,'python':sys.version,'worker_sha256':digest(__file__)})
    emit('prepared',training=len(train),validation=len(test),software=versions)

def preview_checkpoint(request,checkpoint,epoch):
    import cv2,numpy as np,torch,gc
    from deeplabcut.pose_estimation_pytorch.apis.utils import get_pose_inference_runner
    prepared=json.loads((WORK/'prepared.json').read_text());dataset=Path(request['dataset'])
    runner=get_pose_inference_runner(model_config=Path(prepared['pose']),snapshot_path=checkpoint,batch_size=1,device='cuda:0',max_individuals=1)
    checkpoint_hash=digest(checkpoint);errors=[];samples=[];used=set()
    output=WORK/'previews'/f'epoch-{epoch:06d}';output.mkdir(parents=True)
    for row in request['images']:
        check_stop()
        sample_key=(row['split'],row['camera_id']);sample=row['split']!='guard' and sample_key not in used
        if row['split']!='validation' and not sample:continue
        im=cv2.imread(str(dataset/row['path']));pred=runner.inference([cv2.cvtColor(im,cv2.COLOR_BGR2RGB)])[0]['bodyparts'][0]
        truth=np.asarray(row['xy'],float);valid=np.asarray(row['valid'],bool)&np.isfinite(pred[:,:2]).all(axis=1)
        if pred.shape!=(len(truth),3):raise ValueError('Checkpoint keypoint count mismatch')
        if row['split']=='validation':errors.extend(np.linalg.norm(pred[valid,:2]-truth[valid],axis=1).tolist())
        if sample:
            used.add(sample_key);draw=im.copy()
            for x,y in truth[np.asarray(row['valid'],bool)]:cv2.circle(draw,(round(x),round(y)),3,(255,70,255),1,cv2.LINE_AA)
            for x,y,confidence in pred:
                if math.isfinite(float(x)) and math.isfinite(float(y)):cv2.drawMarker(draw,(round(x),round(y)),(255,230,60),cv2.MARKER_CROSS,6,1)
            points=truth[np.asarray(row['valid'],bool)]
            lo=np.maximum(np.floor(points.min(axis=0)-20),0).astype(int);hi=np.minimum(np.ceil(points.max(axis=0)+20),[im.shape[1],im.shape[0]]).astype(int)
            full=cv2.resize(draw,(640,360));crop=draw[lo[1]:hi[1],lo[0]:hi[0]]
            crop=cv2.resize(crop,(round(crop.shape[1]*360/crop.shape[0]),360));canvas=np.hstack([full,crop])
            name=f"{row['split']}-{row['camera_id']}.png";cv2.imwrite(str(output/name),canvas)
            sample_id=row['split']+'-'+row['camera_id'];relative=(output/name).relative_to(WORK).as_posix()
            emit('preview',id=sample_id,label=f"{row['split']} · {row['camera_id']} · frame {row['source_frame']} · magenta labels / cyan predictions",path=relative,step=epoch,checkpoint_id=checkpoint.name+':'+checkpoint_hash[:12])
            samples.append({'image_id':row['image_id'],'path':relative,'keypoints':pred.tolist()})
    if errors:
        emit('metric',id='validation_mean_px',label='Validation keypoint error',unit='px',step=epoch,value=float(np.mean(errors)))
        emit('metric',id='validation_p95_px',label='Validation 95th percentile error',unit='px',step=epoch,value=float(np.percentile(errors,95)))
    atomic(output/'predictions.json',{'epoch':epoch,'checkpoint':str(checkpoint),'checkpoint_sha256':checkpoint_hash,'samples':samples,'validation_distances_px':errors})
    del runner;gc.collect();torch.cuda.empty_cache()
    emit('checkpoint',path=checkpoint.relative_to(WORK).as_posix(),sha256=checkpoint_hash,epoch=epoch)

def select_refinement_examples(candidates, limit, spacing_ns):
    """Balance error groups and spread samples in source time within each camera."""
    groups={name:sorted((r for r in candidates if r['group']==name),key=lambda r:(-r['score'],r['source_frame'],r['camera_id'])) for name in ('near_miss','major_failure')}
    selected=[]
    def take(group):
        while groups[group]:
            row=groups[group].pop(0)
            if all(row['camera_id']!=other['camera_id'] or abs(int(row['timestamp_ns'])-int(other['timestamp_ns']))>=spacing_ns for other in selected):
                selected.append(row);return True
        return False
    while len(selected)<limit:
        counts={g:sum(r['group']==g for r in selected) for g in groups}
        order=sorted(groups,key=lambda g:counts[g])
        if not any(take(g) for g in order):break
    return selected


def mine(request):
    import cv2,numpy as np,torch,gc
    from deeplabcut.pose_estimation_pytorch.apis.utils import get_pose_inference_runner
    if digest(request['checkpoint'])!=request['checkpoint_sha256']:raise ValueError('Mining checkpoint changed')
    runner=get_pose_inference_runner(model_config=Path(request['pose_config']),snapshot_path=Path(request['checkpoint']),batch_size=1,device='cuda:0',max_individuals=1)
    references=request['references'];candidates=[];counts={'scanned':0,'needs_geometry':0,'already_reviewed':0,'reserved':0,'near_miss':0,'major_failure':0,'agreement':0};total=len(request['source_frames'])*len(request['videos'])
    def finite_list(array):return [[float(v) if math.isfinite(float(v)) else None for v in row] for row in array]
    with (WORK/'predictions.jsonl').open('w',encoding='utf-8') as output:
        for camera,video in request['videos'].items():
            capture=cv2.VideoCapture(video)
            try:
                for local,(frame,stamp) in enumerate(zip(request['source_frames'],request['timestamps_ns'])):
                    check_stop();ok,image=capture.read()
                    if not ok:raise ValueError('Synchronized video ended before its source timing index')
                    pred=runner.inference([cv2.cvtColor(image,cv2.COLOR_BGR2RGB)])[0]['bodyparts'][0]
                    if pred.shape!=(request['keypoint_count'],3):raise ValueError('Prediction keypoint definition mismatch')
                    key=f'{frame}:{camera}';reference=references.get(key);group='needs_geometry';score=0.0;reason='No verified prepared pose for this image';normalized_error=None
                    if key in request['reviewed_keys']:group='already_reviewed';reason='Already reviewed in the current dataset'
                    elif int(stamp)>=int(request['training_cutoff_ns']):group='reserved';reason='Reserved validation or temporal guard interval'
                    elif reference:
                        truth=np.asarray(reference['xy'],dtype=float);valid=np.isfinite(truth).all(axis=1)&(truth[:,0]>=0)&(truth[:,0]<image.shape[1])&(truth[:,1]>=0)&(truth[:,1]<image.shape[0])
                        finite=np.isfinite(pred[:,:2]).all(axis=1);confident=finite&(pred[:,2]>=request['confidence_threshold'])
                        if valid.any():
                            scale=max(float(np.linalg.norm(np.ptp(truth[valid],axis=0))),1.0)
                            comparable=valid&finite
                            normalized_error=float(np.median(np.linalg.norm(pred[comparable,:2]-truth[comparable],axis=1))/scale) if comparable.any() else None
                            fraction=float(confident[valid].mean())
                            if fraction<.5 or normalized_error is None or normalized_error>=request['major_error_threshold']:
                                group='major_failure';score=max(normalized_error or 0,1-fraction);reason=f'Major disagreement or missing prediction; {fraction:.0%} of reference points confidently detected'
                            elif normalized_error>=request['near_error_threshold']:
                                group='near_miss';score=normalized_error;reason=f'Median point error is {normalized_error:.1%} of projected target size'
                            else:group='agreement';reason='Prediction agrees with the prepared pose within the configured threshold'
                    row={'source_frame':frame,'local_frame':local,'camera_id':camera,'timestamp_ns':str(stamp),'key':key,'group':group,'score':score,'reason':reason,'normalized_error':normalized_error,'prediction':finite_list(pred)}
                    output.write(json.dumps(row,allow_nan=False)+'\n');counts['scanned']+=1;counts[group]+=1
                    if group in ('near_miss','major_failure'):candidates.append(row)
                    if counts['scanned']%10==0:emit('scan_progress',completed=counts['scanned'],total=total)
            finally:capture.release()
    selected=select_refinement_examples(candidates,request['image_limit'],round(request['spacing_seconds']*1_000_000_000))
    (WORK/'previews').mkdir(exist_ok=True)
    for row in selected:
        check_stop();capture=cv2.VideoCapture(request['videos'][row['camera_id']]);capture.set(cv2.CAP_PROP_POS_FRAMES,row['local_frame']);ok,image=capture.read();capture.release()
        if not ok:raise ValueError('Unable to decode proposed review image')
        truth=np.asarray(references[row['key']]['xy'],dtype=float);pred=np.asarray(row['prediction'],dtype=float)
        for x,y in truth[np.isfinite(truth).all(axis=1)]:cv2.circle(image,(round(x),round(y)),3,(255,70,255),1,cv2.LINE_AA)
        for x,y,c in pred:
            if np.isfinite([x,y]).all():cv2.drawMarker(image,(round(x),round(y)),(255,230,60),cv2.MARKER_CROSS,8,1)
        points=truth[np.isfinite(truth).all(axis=1)];lo=np.maximum(np.floor(points.min(axis=0)-30),0).astype(int);hi=np.minimum(np.ceil(points.max(axis=0)+30),[image.shape[1],image.shape[0]]).astype(int)
        crop=image[lo[1]:hi[1],lo[0]:hi[0]];full=cv2.resize(image,(640,360))
        if crop.size:crop=cv2.resize(crop,(max(1,round(crop.shape[1]*360/crop.shape[0])),360));full=np.hstack([full,crop])
        row['preview']=f"previews/{row['source_frame']:09d}-{row['camera_id']}.png";cv2.imwrite(str(WORK/row['preview']),full)
    atomic(WORK/'result.json',{'counts':counts,'proposals':selected,'checkpoint_sha256':request['checkpoint_sha256'],'scope':'Full synchronized recording; additions require an existing verified pose reference','settings':{k:request[k] for k in ('image_limit','spacing_seconds','confidence_threshold','near_error_threshold','major_error_threshold')}})
    emit('scan_progress',completed=total,total=total)
    del runner;gc.collect();torch.cuda.empty_cache()


def train(request):
    import torch,cv2,numpy as np,random,gc
    from deeplabcut.pose_estimation_pytorch.runners.logger import LOGGER,BaseLogger
    from deeplabcut.pose_estimation_pytorch.apis.training import train as dlc_train
    from deeplabcut.pose_estimation_pytorch.data.dlcloader import DLCLoader
    from deeplabcut.pose_estimation_pytorch.task import Task
    if not torch.cuda.is_available():raise ValueError('CUDA is unavailable in the selected training environment')
    torch.set_num_threads(2);cv2.setNumThreads(1);random.seed(request['seed']);np.random.seed(request['seed']);torch.manual_seed(request['seed'])
    class SkellyClickerLogger(BaseLogger):
        def __init__(self, **kwargs):pass
        def log_config(self,config=None):pass
        def save(self):pass
        def log(self,metrics,step=None):
            check_stop()
            for key,label in [('losses/train.total_loss','Training loss'),('losses/eval.total_loss','Validation loss')]:
                value=metrics.get(key)
                if value is not None and math.isfinite(float(value)):emit('metric',id=key.replace('/','_').replace('.','_'),label=label,unit='loss',step=step,value=float(value))
            emit('progress',epoch=step,detail='Evaluation' if any(k.startswith('losses/eval') for k in metrics) else 'Training')
    LOGGER.register_module(module=SkellyClickerLogger)
    prepared=json.loads((WORK/'prepared.json').read_text());checkpoint=None;epoch=0
    if request.get('initial_checkpoint'):
        source=Path(request['initial_checkpoint'])
        if digest(source)!=request['initial_checkpoint_sha256']:raise ValueError('Parent checkpoint changed')
        saved=torch.load(source,map_location='cpu',weights_only=True)
        # New dataset round: retain backbone AND object head; reset optimizer,
        # scheduler and epoch. Official DLC loads the complete model [@dlcTraining302].
        checkpoint=WORK/'initial-weights.pt'
        torch.save({'model':saved['model'],'metadata':{'epoch':0}},checkpoint)
        del saved
        emit('initialization',mode='model_weights_with_fresh_optimizer',parent_sha256=request['initial_checkpoint_sha256'])
    # Bounded official API calls allow immutable checkpoint previews and cooperative stop.
    # DLC resumes optimizer/scheduler and interprets epochs as additional epochs.
    while epoch<request['epochs']:
        check_stop();count=min(request['save_every'],request['epochs']-epoch)
        emit('progress',epoch=epoch,detail='Training')
        loader=DLCLoader(Path(prepared['config']),shuffle=1)
        loader.model_cfg.train_settings.epochs=count
        # The file config restricts logger names; the official lower-level API
        # explicitly accepts a registry logger_config without changing that schema.
        dlc_train(loader=loader,run_config=loader.model_cfg,task=Task(loader.model_cfg.get('method','bu')),device='cuda:0',logger_config={'type':'SkellyClickerLogger'},snapshot_path=checkpoint,max_snapshots_to_keep=5)
        del loader
        epoch+=count;folder=Path(prepared['pose']).parent
        candidates=[p for p in folder.glob('snapshot-*.pt') if p.stem.split('-')[-1].isdigit()]
        checkpoint=max(candidates,key=lambda p:int(p.stem.split('-')[-1]))
        state=torch.load(checkpoint,map_location='cpu',weights_only=True)
        if state['metadata']['epoch']!=epoch:raise ValueError('Saved checkpoint epoch differs from requested progress')
        del state;gc.collect();torch.cuda.empty_cache();check_stop()
        import shutil
        published=WORK/'checkpoints'/f'epoch-{epoch:06d}.pt';published.parent.mkdir(exist_ok=True)
        shutil.copyfile(checkpoint,published)
        if digest(published)!=digest(checkpoint):raise ValueError('Checkpoint publication changed bytes')
        checkpoint=published
        preview_checkpoint(request,checkpoint,epoch)
    atomic(WORK/'trained.json',{'epochs':epoch,'checkpoint':checkpoint.relative_to(WORK).as_posix(),'checkpoint_sha256':digest(checkpoint),'dataset_sha256':request['dataset_sha256']})
    emit('complete',epochs=epoch)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['prepare','train','mine']);parser.add_argument('work',type=Path);args=parser.parse_args();WORK=args.work.resolve()
    try:
        request=json.loads((WORK/'worker-request.json').read_text());check_stop()
        {'prepare':prepare,'train':train,'mine':mine}[args.mode](request)
    except RequestedStop:emit('cancelled');sys.exit(2)
    except Exception as error:emit('error',message=str(error),traceback=traceback.format_exc());raise
