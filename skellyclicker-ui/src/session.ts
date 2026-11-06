export type SessionState={project_path:string|null;recording_id:string|null;workspace:'viewer'|'training';sidebar:'images'|'project';training_run_id:string|null};
export const emptySession:SessionState={project_path:null,recording_id:null,workspace:'viewer',sidebar:'images',training_run_id:null};
