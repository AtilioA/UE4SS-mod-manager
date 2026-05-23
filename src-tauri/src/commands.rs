use std::collections::HashMap;
use std::path::Path;
use crate::error::ModError;
use crate::mod_manager::models::{UE4SSMod, LuaConfigEntry, AppConfig};
use crate::mod_manager::service;
use crate::mod_manager::config_parser::LuaConfigDocument;

#[tauri::command]
pub async fn detect_mods_folder() -> Result<Option<String>, ModError> {
    Ok(service::detect_mods_folder().map(|p| p.to_string_lossy().to_string()))
}

#[tauri::command]
pub async fn load_mods(mods_folder: String) -> Result<Vec<UE4SSMod>, ModError> {
    service::load_mods(Path::new(&mods_folder))
}

#[tauri::command]
pub async fn install_mod(
    mods_folder: String,
    source_path: String,
    replace: bool,
) -> Result<UE4SSMod, ModError> {
    let mods_path = Path::new(&mods_folder);
    let src_path = Path::new(&source_path);

    if !src_path.exists() {
        return Err(ModError::InvalidMod("The specified path does not exist on disk.".to_string()));
    }

    if src_path.is_file() {
        let ext = src_path.extension().and_then(|e| e.to_str()).map(|s| s.to_lowercase());
        match ext.as_deref() {
            Some("zip") | Some("7z") | Some("rar") => {
                service::install_mod_archive(mods_path, src_path, replace)
            }
            _ => {
                Err(ModError::InvalidMod("Unsupported archive format. Only ZIP (.zip), 7-Zip (.7z), and RAR (.rar) archives or mod folders are supported.".to_string()))
            }
        }
    } else if src_path.is_dir() {
        service::install_mod_folder(mods_path, src_path, replace)
    } else {
        Err(ModError::InvalidMod("Dropped item is neither a file nor a directory.".to_string()))
    }
}

#[tauri::command]
pub async fn save_changes(
    mods_folder: String,
    mods: Vec<UE4SSMod>,
    save_enabled: bool,
    save_json: bool,
    save_txt: bool,
) -> Result<(), ModError> {
    service::save_changes(Path::new(&mods_folder), &mods, save_enabled, save_json, save_txt)
}

#[tauri::command]
pub async fn load_mod_config(config_path: String) -> Result<Vec<LuaConfigEntry>, ModError> {
    let doc = LuaConfigDocument::from_path(Path::new(&config_path))?;
    Ok(doc.get_entries())
}

#[tauri::command]
pub async fn save_mod_config(
    config_path: String,
    updates: HashMap<String, serde_json::Value>,
) -> Result<(), ModError> {
    let mut doc = LuaConfigDocument::from_path(Path::new(&config_path))?;
    doc.save(&updates)
}

#[tauri::command]
pub async fn launch_game(mods_folder: String) -> Result<String, ModError> {
    service::launch_game(Path::new(&mods_folder))
}

#[tauri::command]
pub async fn pick_mods_folder() -> Result<Option<String>, ModError> {
    let folder = rfd::FileDialog::new()
        .set_title("Select UE4SS Mods Folder")
        .pick_folder();
    Ok(folder.map(|p| p.to_string_lossy().to_string()))
}

#[tauri::command]
pub async fn open_mods_folder(mods_folder: String) -> Result<(), ModError> {
    let path = Path::new(&mods_folder);
    if !path.exists() {
        return Err(ModError::InvalidModFolder("Directory does not exist".to_string()));
    }
    
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer")
            .arg(path)
            .spawn()
            .map_err(ModError::Io)?;
    }
    
    #[cfg(target_os = "macos")]
    {
        std::process::Command::new("open")
            .arg(path)
            .spawn()
            .map_err(ModError::Io)?;
    }
    
    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(path)
            .spawn()
            .map_err(ModError::Io)?;
    }
    
    Ok(())
}

#[tauri::command]
pub async fn load_app_config() -> Result<AppConfig, ModError> {
    Ok(service::load_app_config())
}

#[tauri::command]
pub async fn save_app_config(config: AppConfig) -> Result<(), ModError> {
    service::save_app_config(&config)
}

#[tauri::command]
pub async fn uninstall_mod(mods_folder: String, mod_name: String) -> Result<(), ModError> {
    service::uninstall_mod(Path::new(&mods_folder), &mod_name)
}

#[tauri::command]
pub async fn load_ue4ss_settings(mods_folder: String) -> Result<Vec<crate::mod_manager::models::Ue4ssSettingsEntry>, ModError> {
    service::load_ue4ss_settings(Path::new(&mods_folder))
}

#[tauri::command]
pub async fn save_ue4ss_settings(
    mods_folder: String,
    updates: HashMap<String, String>,
) -> Result<(), ModError> {
    service::save_ue4ss_settings(Path::new(&mods_folder), updates)
}

