import type {ReactNode} from 'react';
import logo from './assets/skellyclicker-logo.svg';

/** Product chrome around the SDK-owned playback workspace. */
export function AppShell({children, sidebar, status, bottom}: {
  children: ReactNode;
  sidebar: ReactNode;
  status: ReactNode;
  bottom?: ReactNode;
}) {
  return <div className="skellyclicker-app">
    <aside className="skellyclicker-sidebar">
      <header><img src={logo} alt="SkellyClicker"/><h1>SkellyClicker</h1></header>
      {sidebar}
    </aside>
    <main className="skellyclicker-main">
      <nav aria-label="Application mode"><span aria-current="page">Playback</span></nav>
      <section className="skellyclicker-workspace" aria-label="Recording playback">{children}</section>
    </main>
    {bottom && <div className="skellyclicker-bottom">{bottom}</div>}
    <footer aria-live="polite">{status}</footer>
  </div>;
}

