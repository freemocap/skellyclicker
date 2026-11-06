import {ButtonSm} from '@freemocap/ui';
export function TrainingActions({canConfigure,canStart,canCancel,starting,cancelling,onConfigure,onStart,onCancel}:{canConfigure:boolean;canStart:boolean;canCancel:boolean;starting:boolean;cancelling:boolean;onConfigure:()=>void;onStart:()=>void;onCancel:()=>void}){
 return <div className="training-command-group" role="group" aria-label="Training actions">
  <ButtonSm text="Configure training" buttonType="secondary" textColor="" iconClass="settings-icon" disabled={!canConfigure} onClick={onConfigure}/>
  <ButtonSm text="Start training" buttonType="primary accent" textColor="" iconClass="play-icon" disabled={!canStart} ariaBusy={starting} onClick={onStart}/>
  <ButtonSm text="Cancel training" buttonType="secondary btn-danger" textColor="" iconClass="stop-icon" disabled={!canCancel||cancelling} ariaBusy={cancelling} onClick={onCancel}/>
 </div>;
}
