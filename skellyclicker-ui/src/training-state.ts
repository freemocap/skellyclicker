import type {PipelineSnapshot} from '@freemocap/client';
export function trainingState(snapshot:PipelineSnapshot|null,starting=false,cancelling=false){
 const active=!!snapshot&&['queued','running'].includes(snapshot.status);
 const operation=snapshot?.operations.find(o=>o.status==='running');
 const train=snapshot?.operations.find(o=>o.operation_id==='train_model');
 let stage='Ready';
 if(starting)stage='Starting';
 else if(active&&(cancelling||snapshot?.cancel_requested))stage='Cancelling';
 else if(snapshot?.status==='complete')stage='Finished';
 else if(snapshot?.status==='failed'&&snapshot.error?.includes('configured maximum duration'))stage='Time limit reached';
 else if(snapshot?.status==='failed')stage='Failed';
 else if(snapshot?.status==='cancelled')stage='Cancelled';
 else if(active){
  if(operation?.operation_id==='freeze_inputs')stage='Preparing inputs';
  else if(operation?.operation_id==='prepare_trainer')stage='Preparing DeepLabCut';
  else if(operation?.operation_id==='publish_run')stage='Saving results';
  else if(operation?.operation_id==='train_model')stage=operation.detail?.toLowerCase().includes('evaluat')?'Evaluating':'Training';
  else stage='Queued';
 }
 const epoch=train?.unit==='epochs'&&train.completed!=null&&train.total!=null?{completed:train.completed,total:train.total}:null;
 return {stage,active,busy:starting||active,cancelling:active&&(cancelling||!!snapshot?.cancel_requested),epoch};
}
