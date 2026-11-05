import type {ReactNode} from 'react';
import {ResizablePanelGroup,ResizablePanel,ResizableHandle} from '@freemocap/ui';
import logo from './assets/skellyclicker-logo.svg';

/** Product controls compose the SDK's shared pane and playback machinery. */
export function AppShell({children, sidebar, status, bottom, connection}: {
  children: ReactNode; sidebar: ReactNode; status: ReactNode; bottom?: ReactNode; connection?: ReactNode;
}) {
  return <div className="skellyclicker-app">
    <ResizablePanelGroup direction="horizontal" autoSaveId="skellyclicker-main-layout" className="skellyclicker-top-panes">
      <ResizablePanel defaultSize={24} minSize={12} maxSize={50}>
        <aside className="skellyclicker-sidebar">
          <header>{connection}<div className="skellyclicker-brand"><img src={logo} alt="SkellyClicker"/><h1>SkellyClicker</h1></div></header>
          {sidebar}
        </aside>
      </ResizablePanel>
      <ResizableHandle aria-label="Resize project sidebar"/>
      <ResizablePanel defaultSize={76} minSize={35}>
        <main className="skellyclicker-main">
          <nav className="skellyclicker-tabs" role="tablist" aria-label="Workspace views"><button id="project-tab" type="button" role="tab" aria-selected="true" aria-controls="project-view">Project</button></nav>
          <section id="project-view" role="tabpanel" aria-labelledby="project-tab" className="skellyclicker-workspace">{children}</section>
        </main>
      </ResizablePanel>
    </ResizablePanelGroup>
    {bottom && <div className="skellyclicker-bottom">{bottom}</div>}
    <footer aria-live="polite">{status}</footer>
  </div>;
}
