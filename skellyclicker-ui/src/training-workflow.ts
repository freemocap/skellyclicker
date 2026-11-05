import type {PipelineGraph} from '@freemocap/ui';

/** App-owned artifact semantics; this includes manual gates, not an executable promise. */
const port = (name: string, kind: string) => ({name, contract: {
  kind, data_granularity: 'recording' as const, namespace: 'skellyclicker.training.v1',
  reference_frame: null, units: null,
}});
const node = (id: string, inputs: ReturnType<typeof port>[], outputs: ReturnType<typeof port>[], manual=false) => ({
  id, operation:id, execution_resource:manual?'human':'compute', stage:id,
  effects: manual ? ['display','write_disk'] as ('display'|'write_disk')[] : ['read_record'] as ('read_record')[], inputs, outputs,
});
const edge = (from:string, output:string, to:string, input:string) => ({source:{node:from,port:output}, target:{node:to,port:input}, binding:'same_key' as const});
export const trainingGraph: PipelineGraph = {
  definition:{nodes:[
    node('source_inputs',[],[port('recording','linked_recording'),port('target','stl_target')]),
    node('extract_images',[port('recording','linked_recording')],[port('images','synchronized_images'),port('calibration','rectified_calibration')]),
    node('stereo_3d',[port('images','synchronized_images'),port('calibration','rectified_calibration')],[port('depth','stereo_geometry')]),
    node('fit_stl',[port('target','stl_target'),port('images','synchronized_images'),port('calibration','rectified_calibration'),port('depth','stereo_geometry')],[port('poses','stl_pose_candidates')]),
    node('generate_candidates',[port('target','stl_target'),port('images','synchronized_images'),port('calibration','rectified_calibration'),port('poses','stl_pose_candidates')],[port('labels','generated_labels')]),
    node('review_labels',[port('labels','generated_labels'),port('images','synchronized_images'),port('poses','stl_pose_candidates')],[port('reviewed','reviewed_labels')],true),
    node('publish_dataset',[port('reviewed','reviewed_labels'),port('images','synchronized_images')],[port('dataset','approved_dataset')]),
  ],edges:[
    edge('source_inputs','recording','extract_images','recording'),
    edge('extract_images','images','stereo_3d','images'),edge('extract_images','calibration','stereo_3d','calibration'),
    edge('source_inputs','target','fit_stl','target'),edge('extract_images','images','fit_stl','images'),edge('extract_images','calibration','fit_stl','calibration'),edge('stereo_3d','depth','fit_stl','depth'),
    edge('source_inputs','target','generate_candidates','target'),edge('extract_images','images','generate_candidates','images'),edge('extract_images','calibration','generate_candidates','calibration'),edge('fit_stl','poses','generate_candidates','poses'),
    edge('generate_candidates','labels','review_labels','labels'),edge('extract_images','images','review_labels','images'),edge('fit_stl','poses','review_labels','poses'),
    edge('review_labels','reviewed','publish_dataset','reviewed'),edge('extract_images','images','publish_dataset','images'),
  ]},topological_order:['source_inputs','extract_images','stereo_3d','fit_stl','generate_candidates','review_labels','publish_dataset'],
};
export interface PreparedSummary {
  frames: {source_frame:number;accepted:boolean;status:string}[];
  accepted:number;
  mask_preset?:string;
  calibration:{source_frame_count:number;image_width:number;image_height:number;depth_method?:string;depth_units?:string};
}
export interface TrainingConfig {
  mode:'reuse'|'fresh'; first:string; count:string; step:string; limit:string; fit:'all'|'passed'|'failed';
}
export function defaultConfig(summary:PreparedSummary|null):TrainingConfig {
  const frames=summary?.frames??[];
  return {mode:frames.length?'reuse':'fresh',first:String(frames[0]?.source_frame??0),count:String(frames.length||30),step:'1',limit:'',fit:'all'};
}
const integer=(value:string,min:number,max=Number.MAX_SAFE_INTEGER)=>value.trim()!==''&&Number.isSafeInteger(Number(value))&&Number(value)>=min&&Number(value)<=max;
export function validateConfig(config:TrainingConfig,summary:PreparedSummary|null):string[] {
  const errors:string[]=[];
  if(!integer(config.first,0))errors.push('First source frame must be a non-negative integer.');
  if(!integer(config.count,1,900))errors.push('Frame count must be an integer from 1 to 900 for the current adapter.');
  if(!integer(config.step,1))errors.push('Candidate stride must be a positive integer.');
  if(config.limit!==''&&!integer(config.limit,1))errors.push('Maximum moments must be empty or a positive integer.');
  if(errors.length)return errors;
  const start=Number(config.first),end=start+Number(config.count);
  if(summary&&end>summary.calibration.source_frame_count)errors.push('The requested range exceeds the recording.');
  if(config.mode==='reuse') {
    if(!summary)errors.push('No prepared result is available to reuse.');
    else {
      const ids=new Set(summary.frames.map(f=>f.source_frame));
      if(Array.from({length:Number(config.count)},(_,i)=>start+i).some(f=>!ids.has(f)))errors.push('Reuse requires every source frame in the requested range to exist in the prepared result.');
    }
  }
  return errors;
}
export function candidateFrames(config:TrainingConfig,summary:PreparedSummary|null):number[] {
  if(config.mode!=='reuse'||!summary||validateConfig(config,summary).length)return [];
  const first=Number(config.first),end=first+Number(config.count);
  const frames=summary.frames.filter(f=>f.source_frame>=first&&f.source_frame<end&&(config.fit==='all'||f.accepted===(config.fit==='passed'))).sort((a,b)=>a.source_frame-b.source_frame);
  return frames.filter((_,i)=>i%Number(config.step)===0).slice(0,config.limit===''?undefined:Number(config.limit)).map(f=>f.source_frame);
}
export function readConfig(value:unknown):TrainingConfig|null {
  if(!value||typeof value!=='object')return null;
  const v=value as Record<string,unknown>;
  if(!['reuse','fresh'].includes(String(v.mode))||!['all','passed','failed'].includes(String(v.fit))||!['first','count','step','limit'].every(k=>typeof v[k]==='string'))return null;
  return {mode:v.mode as TrainingConfig['mode'],fit:v.fit as TrainingConfig['fit'],first:v.first as string,count:v.count as string,step:v.step as string,limit:v.limit as string};
}
