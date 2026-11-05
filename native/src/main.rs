#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use freemocap_desktop::BackendProcess;
use std::{io, sync::Mutex, time::Duration};
use tauri::Manager;
struct DesktopState(Mutex<BackendProcess>);

#[tauri::command]
fn backend_url(state: tauri::State<'_, DesktopState>) -> Result<String, String> {
    state
        .0
        .lock()
        .map(|backend| backend.base_url().to_owned())
        .map_err(|error| error.to_string())
}

fn main() {
    let app = tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![backend_url])
        .setup(|app| {
            let executable = app
                .path()
                .resource_dir()?
                .join("backend")
                .join(if cfg!(windows) {
                    "skellyclicker-backend.exe"
                } else {
                    "skellyclicker-backend"
                });
            let backend = BackendProcess::spawn(&executable, &[], Duration::from_secs(30))?;
            app.manage(DesktopState(Mutex::new(backend)));
            // State precedes webview creation, following SkellySpeak's startup ordering.
            // [@skellyspeakDesktopReference]
            let config = app
                .config()
                .app
                .windows
                .iter()
                .find(|window| window.label == "main")
                .ok_or_else(|| io::Error::other("Main window configuration is missing"))?;
            tauri::WebviewWindowBuilder::from_config(app, config)?.build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Unable to start SkellyClicker desktop application");
    app.run(|handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(state) = handle.try_state::<DesktopState>() {
                if let Ok(mut backend) = state.0.lock() {
                    if let Err(error) = backend.shutdown() {
                        eprintln!("Backend shutdown failed: {error}");
                    }
                }
            }
        }
    });
}
