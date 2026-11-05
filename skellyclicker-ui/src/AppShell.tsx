import type {ReactNode} from 'react';
import logo from './assets/skellyclicker-logo.svg';

/** Product chrome around the SDK-owned playback workspace. */
export function AppShell({children, sidebar, status, bottom, connection}: {
  children: ReactNode;
  sidebar: ReactNode;
  status: ReactNode;
  bottom?: ReactNode;
  connection?: ReactNode;
}) {
  return <div className="skellyclicker-app">
    <aside className="skellyclicker-sidebar">
      <header>{connection}<div className="skellyclicker-brand"><img src={logo} alt="SkellyClicker"/><h1>SkellyClicker</h1></div></header>
      {sidebar}
    </aside>
    <main className="skellyclicker-main">
      <nav className="skellyclicker-tabs" role="tablist" aria-label="Workspace views"><button id="project-tab" type="button" role="tab" aria-selected="true" aria-controls="project-view">Project</button></nav>
      <section id="project-view" role="tabpanel" aria-labelledby="project-tab" className="skellyclicker-workspace">{children}</section>
    </main>
    {bottom && <div className="skellyclicker-bottom">{bottom}</div>}
    <footer aria-live="polite">{status}</footer>
  </div>;
}



