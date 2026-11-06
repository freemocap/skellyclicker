import {useEffect,useRef,useState,type ReactNode} from 'react';
import {ResizablePanelGroup,ResizablePanel,ResizableHandle,WorkspaceTabs,ButtonSm,type ResizablePanelHandle} from '@freemocap/ui';
import logo from './assets/skellyclicker-logo.svg';
export type WorkspaceView='viewer'|'generation'|'training';
/** Product composition; all visual controls and resizing come from the public SDK. */
export function AppShell({children,sidebar,bottom,connection,training,generation,view,onView,projectName,onCreateTrainingSet,onToolbarTarget,sidebarRequest=0}:{
 children:ReactNode;sidebar:ReactNode;sidebarRequest?:number;bottom?:ReactNode;connection?:ReactNode;training?:ReactNode;generation?:ReactNode;
 view:WorkspaceView;onView:(view:WorkspaceView)=>void;projectName?:string;onCreateTrainingSet?:()=>void;onToolbarTarget?:(element:HTMLDivElement|null)=>void;
}){
 const sidebarRef=useRef<ResizablePanelHandle>(null);
 const [sidebarOpen,setSidebarOpen]=useState(false);
 useEffect(()=>{if(sidebarRequest)sidebarRef.current?.expand();},[sidebarRequest]);
 return <div className="skellyclicker-app">
  <header className="clicker-header"><div className="skellyclicker-brand"><img src={logo} alt=""/><h1>SkellyClicker</h1></div><span>{projectName??'Open a project'}</span><div className="clicker-connection">{connection}</div></header>
  <div className="clicker-navigation"><WorkspaceTabs value={view} onChange={value=>onView(value as WorkspaceView)} tabs={[{id:'viewer',label:'Viewer',panelId:'viewer-view'},{id:'generation',label:'Generate training data',panelId:'generation-view'},{id:'training',label:'Training',panelId:'results-view'}]}/><div className="clicker-navigation-actions"><ButtonSm text={sidebarOpen?'Hide project / images':'Project / images'} buttonType="secondary" textColor="" ariaExpanded={sidebarOpen} onClick={()=>{if(sidebarOpen)sidebarRef.current?.collapse();else sidebarRef.current?.expand();}}/><ButtonSm text="Create image training set" buttonType="secondary" textColor="" disabled={!onCreateTrainingSet} onClick={onCreateTrainingSet}/></div></div>
  <div ref={onToolbarTarget} className="clicker-command-slot" style={{display:view==='generation'?'none':undefined}}/>
  <ResizablePanelGroup direction="horizontal" autoSaveId="skellyclicker-main-layout" className={`skellyclicker-top-panes ${view==='generation'?'generation-layout':''}`}>
   <ResizablePanel ref={sidebarRef} defaultSize={0} minSize={18} maxSize={50} collapsible collapsedSize={0} onCollapse={()=>setSidebarOpen(false)} onExpand={()=>setSidebarOpen(true)}>
    <aside className="skellyclicker-sidebar" inert={!sidebarOpen||view==='generation'} aria-label="Project and training images"><div className="skellyclicker-sidebar-content">{sidebar}</div></aside>
   </ResizablePanel>
   <ResizableHandle aria-label="Resize project sidebar"/>
   <ResizablePanel defaultSize={100} minSize={35}><main className="skellyclicker-main"><div className="workspace-panels">
    <section id="viewer-view" role="tabpanel" aria-label="Viewer" aria-hidden={view!=='viewer'} className="skellyclicker-workspace" inert={view!=='viewer'} style={{visibility:view==='viewer'?'visible':'hidden',opacity:view==='viewer'?1:0,pointerEvents:view==='viewer'?'auto':'none'}}>{children}</section>
    <section id="generation-view" role="tabpanel" aria-label="Generate training data" aria-hidden={view!=='generation'} className="skellyclicker-workspace" inert={view!=='generation'} style={{visibility:view==='generation'?'visible':'hidden',opacity:view==='generation'?1:0,pointerEvents:view==='generation'?'auto':'none'}}>{generation}</section>
    <section id="results-view" role="tabpanel" aria-label="Training" aria-hidden={view==='viewer'||view==='generation'} className="skellyclicker-workspace" inert={view==='viewer'||view==='generation'} style={{visibility:(view==='training')?'visible':'hidden',opacity:(view==='training')?1:0,pointerEvents:(view==='training')?'auto':'none'}}>{training}</section>
   </div></main></ResizablePanel>
  </ResizablePanelGroup>
  {bottom&&<div className="skellyclicker-bottom">{bottom}</div>}
 </div>;
}
