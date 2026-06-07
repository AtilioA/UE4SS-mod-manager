#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod commands;
mod error;
mod mod_manager;

fn main() {
    // Initialize logging using env_logger
    env_logger::init();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::detect_mods_folder,
            commands::load_mods,
            commands::install_mod,
            commands::save_changes,
            commands::load_mod_config,
            commands::save_mod_config,
            commands::launch_game,
            commands::pick_mods_folder,
            commands::open_mods_folder,
            commands::open_path,
            commands::load_app_config,
            commands::save_app_config,
            commands::uninstall_mod,
            commands::load_ue4ss_settings,
            commands::save_ue4ss_settings
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
