import {type ReactNode} from 'react';
import {ResizablePanelGroup,ResizablePanel,ResizableHandle} from '@freemocap/ui';
import logo from './assets/skellyclicker-logo.svg';

/** Product controls compose the SDK's shared pane and playback machinery. */
export function AppShell({children, sidebar, bottom, connection, training, view, onView}: {
  children: ReactNode; sidebar: ReactNode; bottom?: ReactNode; connection?: ReactNode; training?: ReactNode; view: 'viewer'|'training'; onView:(view:'viewer'|'training')=>void;
}) {
  return <div className="skellyclicker-app">
    <ResizablePanelGroup direction="horizontal" autoSaveId="skellyclicker-main-layout" className="skellyclicker-top-panes">
      <ResizablePanel defaultSize={24} minSize={12} maxSize={50}>
        <aside className="skellyclicker-sidebar">
          <header>{connection}<div className="skellyclicker-brand"><img src={logo} alt="SkellyClicker"/><h1>SkellyClicker</h1></div></header>
          <div className="skellyclicker-sidebar-content">{sidebar}</div>
        </aside>
      </ResizablePanel>
      <ResizableHandle aria-label="Resize project sidebar"/>
      <ResizablePanel defaultSize={76} minSize={35}>
        <main className="skellyclicker-main">
          <nav className="skellyclicker-tabs" role="tablist" aria-label="Workspace views">{(['viewer','training'] as const).map(tab=><button key={tab} id={tab+'-tab'} type="button" role="tab" aria-selected={view===tab} aria-controls={tab+'-view'} onClick={()=>onView(tab)}>{tab==='viewer'?'Viewer':'Training dashboard'}</button>)}</nav>
          <div className="workspace-panels"><section id="viewer-view" role="tabpanel" aria-labelledby="viewer-tab" aria-hidden={view!=='viewer'} className="skellyclicker-workspace" inert={view!=='viewer'} style={{visibility:view==='viewer'?'visible':'hidden',opacity:view==='viewer'?1:0,pointerEvents:view==='viewer'?'auto':'none'}}>{children}</section><section id="training-view" role="tabpanel" aria-labelledby="training-tab" aria-hidden={view!=='training'} className="skellyclicker-workspace" inert={view!=='training'} style={{visibility:view==='training'?'visible':'hidden',opacity:view==='training'?1:0,pointerEvents:view==='training'?'auto':'none'}}>{training}</section></div>
        </main>
      </ResizablePanel>
    </ResizablePanelGroup>
    {bottom && <div className="skellyclicker-bottom">{bottom}</div>}
  </div>;
}
