use crate::error::ModError;
use crate::mod_manager::models::UE4SSMod;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

pub const NATIVE_MODS: &[&str] = &[
    "BPML_GenericFunctions",
    "BPModLoaderMod",
    "CheatManagerEnablerMod",
    "ConsoleCommandsMod",
    "ConsoleEnablerMod",
    "Keybinds",
    "ConsoleCommands",
];

const MAX_NESTED_MOD_DEPTH: usize = 15;

pub fn detect_mods_folder() -> Option<PathBuf> {
    let current_exe = std::env::current_exe().ok()?;
    let mut current = current_exe.parent()?;

    // Check 1: We are in UE4SS/Mods directly
    if is_mods_folder(current) {
        return Some(current.to_path_buf());
    }

    // Check 2: We are in UE4SS, which contains Mods/
    let mods_in_current = current.join("Mods");
    if mods_in_current.is_dir()
        && current.file_name().map(|n| n.to_ascii_uppercase())
            == Some(std::ffi::OsString::from("UE4SS"))
    {
        return Some(mods_in_current);
    }

    // Check 3: Check up to 4 parent folders
    for _ in 0..4 {
        if is_mods_folder(current) {
            return Some(current.to_path_buf());
        }

        let mods_path = current.join("Mods");
        if mods_path.is_dir()
            && mods_path
                .parent()
                .and_then(|p| p.file_name())
                .map(|n| n.to_ascii_uppercase())
                == Some(std::ffi::OsString::from("UE4SS"))
        {
            return Some(mods_path);
        }

        let ue4ss_path = current.join("UE4SS").join("Mods");
        if ue4ss_path.is_dir() {
            return Some(ue4ss_path);
        }

        if let Some(p) = current.parent() {
            current = p;
        } else {
            break;
        }
    }

    None
}

fn is_mods_folder(path: &Path) -> bool {
    let is_mods =
        path.file_name().map(|n| n.to_ascii_uppercase()) == Some(std::ffi::OsString::from("MODS"));
    let is_parent_ue4ss = path
        .parent()
        .and_then(|p| p.file_name())
        .map(|n| n.to_ascii_uppercase())
        == Some(std::ffi::OsString::from("UE4SS"));
    is_mods && is_parent_ue4ss
}

pub fn load_mods<P: AsRef<Path>>(mods_folder: P) -> Result<Vec<UE4SSMod>, ModError> {
    let mods_folder = mods_folder.as_ref();
    if !mods_folder.is_dir() {
        return Err(ModError::InvalidModFolder(format!(
            "Path '{}' is not a valid directory.",
            mods_folder.display()
        )));
    }

    let mut mods = Vec::new();
    for entry in fs::read_dir(mods_folder)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            let name = match path.file_name().and_then(|n| n.to_str()) {
                Some(n) => n.to_string(),
                None => continue,
            };

            if name.to_uppercase() == "SHARED" {
                continue;
            }

            match load_single_mod(&path) {
                Ok(mut m) => {
                    m.is_native = NATIVE_MODS
                        .iter()
                        .any(|&n| n.to_uppercase() == name.to_uppercase());
                    mods.push(m);
                }
                Err(e) => {
                    log::warn!("Skipping invalid mod at '{}': {}", path.display(), e);
                }
            }
        }
    }

    // Sort mods by name case-insensitively
    mods.sort_by(|a, b| a.name.to_lowercase().cmp(&b.name.to_lowercase()));
    Ok(mods)
}

fn load_single_mod(path: &Path) -> Result<UE4SSMod, ModError> {
    let name = path
        .file_name()
        .and_then(|n| n.to_str())
        .ok_or_else(|| ModError::InvalidMod("Invalid mod folder name".to_string()))?
        .to_string();

    let scripts_dir = path.join("scripts");
    let dlls_dir = path.join("dlls");
    let mut scripts = Vec::new();

    // Read scripts folder
    if scripts_dir.is_dir() {
        for entry in fs::read_dir(&scripts_dir)? {
            let entry = entry?;
            let file_path = entry.path();
            if file_path.is_file() {
                if let Some(ext) = file_path.extension().and_then(|e| e.to_str()) {
                    if ext.eq_ignore_ascii_case("lua") {
                        if let Some(filename) = file_path.file_name().and_then(|f| f.to_str()) {
                            scripts.push(filename.to_string());
                        }
                    }
                }
            }
        }
    }

    // Read dlls folder
    if dlls_dir.is_dir() {
        for entry in fs::read_dir(&dlls_dir)? {
            let entry = entry?;
            let file_path = entry.path();
            if file_path.is_file() {
                if let Some(ext) = file_path.extension().and_then(|e| e.to_str()) {
                    if ext.eq_ignore_ascii_case("dll") {
                        if let Some(filename) = file_path.file_name().and_then(|f| f.to_str()) {
                            scripts.push(filename.to_string());
                        }
                    }
                }
            }
        }
    }

    if scripts.is_empty() {
        return Err(ModError::InvalidMod(format!(
            "Mod '{}' has no lua scripts or dlls.",
            name
        )));
    }

    let has_main_lua = scripts.iter().any(|s| s.eq_ignore_ascii_case("main.lua"));
    let has_main_dll = scripts.iter().any(|s| s.eq_ignore_ascii_case("main.dll"));

    if !has_main_lua && !has_main_dll {
        return Err(ModError::InvalidMod(format!(
            "Mod '{}' has scripts, but is missing a main file (main.lua or main.dll).",
            name
        )));
    }

    let lang = if has_main_lua { "lua" } else { "cpp" }.to_string();
    let enabled = path.join("enabled.txt").is_file();

    let mut config_path = None;
    if scripts_dir.is_dir() {
        for entry in fs::read_dir(&scripts_dir)? {
            let entry = entry?;
            let file_path = entry.path();
            if file_path.is_file() {
                if let Some(filename) = file_path.file_name().and_then(|f| f.to_str()) {
                    if filename.eq_ignore_ascii_case("config.lua") {
                        config_path = Some(file_path.to_string_lossy().to_string());
                        break;
                    }
                }
            }
        }
    }

    Ok(UE4SSMod {
        name,
        path: path.to_string_lossy().to_string(),
        enabled,
        scripts,
        is_native: false,
        lang,
        config_path,
    })
}

fn resolve_mod_path(source_path: &Path) -> Result<PathBuf, ModError> {
    let mut current = source_path.canonicalize()?;

    for _ in 0..MAX_NESTED_MOD_DEPTH {
        // Try to load it. If it successfully loads, we found the mod!
        if load_single_mod(&current).is_ok() {
            return Ok(current);
        }

        // It's not a valid mod. Check if there are any files, or exactly 1 subdirectory
        let mut dirs = Vec::new();
        let mut has_files = false;

        for entry in fs::read_dir(&current)? {
            let entry = entry?;
            let path = entry.path();
            if path.is_file() {
                has_files = true;
                break;
            } else if path.is_dir() {
                dirs.push(path);
            }
        }

        if has_files || dirs.len() != 1 {
            return Err(ModError::InvalidMod(format!(
                "Path '{}' does not seem to have a valid UE4SS structure. Nested mod folders are only supported when no other files are present.",
                source_path.display()
            )));
        }

        current = dirs.remove(0);
    }

    Err(ModError::InvalidMod(format!(
        "Path '{}' doesn't seem to have a valid UE4SS structure. Nested mod folders are limited to {} wrapper folders.",
        source_path.display(),
        MAX_NESTED_MOD_DEPTH
    )))
}

pub fn install_mod_folder<P: AsRef<Path>, Q: AsRef<Path>>(
    mods_folder: P,
    source_path: Q,
    replace: bool,
) -> Result<UE4SSMod, ModError> {
    let mods_folder = mods_folder.as_ref();
    let source_path = source_path.as_ref().canonicalize()?;

    let resolved_src = resolve_mod_path(&source_path)?;
    let mod_name = resolved_src
        .file_name()
        .and_then(|n| n.to_str())
        .ok_or_else(|| ModError::InvalidMod("Invalid mod folder name".to_string()))?;

    let target_path = mods_folder.join(mod_name);

    if resolved_src
        == target_path
            .canonicalize()
            .unwrap_or_else(|_| target_path.clone())
    {
        // Already in the correct destination, enable it
        let mut m = load_single_mod(&target_path)?;
        m.enabled = true;
        fs::write(target_path.join("enabled.txt"), "")?;
        return Ok(m);
    }

    if target_path.exists() {
        if !replace {
            return Err(ModError::ModAlreadyExists(mod_name.to_string()));
        }

        // Security check: Refuse to remove paths outside of the managed mods folder
        if !target_path.starts_with(mods_folder) || target_path == mods_folder {
            return Err(ModError::InvalidMod(format!(
                "Refusing to remove path outside managed mods directory: {}",
                target_path.display()
            )));
        }

        fs::remove_dir_all(&target_path)?;
    }

    copy_dir_all(&resolved_src, &target_path)?;
    fs::write(target_path.join("enabled.txt"), "")?;

    let mut installed_mod = load_single_mod(&target_path)?;
    installed_mod.enabled = true;
    installed_mod.is_native = NATIVE_MODS
        .iter()
        .any(|&n| n.to_uppercase() == installed_mod.name.to_uppercase());

    Ok(installed_mod)
}

pub fn install_mod_archive<P: AsRef<Path>, Q: AsRef<Path>>(
    mods_folder: P,
    archive_path: Q,
    replace: bool,
) -> Result<UE4SSMod, ModError> {
    let mods_folder = mods_folder.as_ref();
    let archive_path = archive_path.as_ref();

    let temp_dir = tempfile::tempdir()?;
    let temp_path = temp_dir.path();

    let ext = archive_path
        .extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_lowercase());
    match ext.as_deref() {
        Some("zip") => {
            let zip_file = fs::File::open(archive_path)?;
            let mut archive = zip::ZipArchive::new(zip_file)?;

            for i in 0..archive.len() {
                let mut file = archive.by_index(i)?;
                let outpath = match file.enclosed_name() {
                    Some(path) => temp_path.join(path),
                    None => continue,
                };

                // Safety check to prevent zip slip
                if !outpath.starts_with(temp_path) {
                    return Err(ModError::InvalidMod(
                        "Unsafe zip entry path detected".to_string(),
                    ));
                }

                if file.name().ends_with('/') {
                    fs::create_dir_all(&outpath)?;
                } else {
                    if let Some(p) = outpath.parent() {
                        let parent_path: &Path = p;
                        if !parent_path.exists() {
                            fs::create_dir_all(parent_path)?;
                        }
                    }
                    let mut outfile = fs::File::create(&outpath)?;
                    std::io::copy(&mut file, &mut outfile)?;
                }
            }
        }
        Some("7z") => {
            sevenz_rust::decompress_file(archive_path, temp_path).map_err(|e| {
                ModError::InvalidMod(format!("Failed to extract 7-Zip archive: {}", e))
            })?;
        }
        Some("rar") => {
            rar::Archive::extract_all(
                &archive_path.to_string_lossy(),
                &temp_path.to_string_lossy(),
                "",
            )
            .map_err(|e| ModError::InvalidMod(format!("Failed to extract RAR archive: {:?}", e)))?;
        }
        _ => {
            return Err(ModError::InvalidMod(
                "Unsupported archive format.".to_string(),
            ))
        }
    }

    let archive_stem = archive_path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("archive_mod");

    let mod_path = archive_mod_path(temp_path, archive_stem)?;
    install_mod_folder(mods_folder, mod_path, replace)
}

fn archive_mod_path(extract_path: &Path, archive_name: &str) -> Result<PathBuf, ModError> {
    let has_scripts = fs::read_dir(extract_path)?.any(|entry| {
        if let Ok(e) = entry {
            let p = e.path();
            p.is_dir()
                && p.file_name()
                    .and_then(|n| n.to_str())
                    .map(|s| s.to_lowercase())
                    == Some("scripts".to_string())
        } else {
            false
        }
    });

    if has_scripts {
        // Mod contents zipped directly, wrap them in a folder named after the archive
        let mod_path = extract_path.join(archive_name);
        fs::create_dir_all(&mod_path)?;

        for entry in fs::read_dir(extract_path)? {
            let entry = entry?;
            let path = entry.path();
            if path != mod_path {
                let target = mod_path.join(path.file_name().unwrap());
                fs::rename(path, target)?;
            }
        }
        return Ok(mod_path);
    }

    let mut folders = Vec::new();
    for entry in fs::read_dir(extract_path)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            folders.push(path);
        }
    }

    if folders.len() == 1 {
        return Ok(folders.remove(0));
    }

    Ok(extract_path.to_path_buf())
}

pub fn save_changes<P: AsRef<Path>>(
    mods_folder: P,
    mods: &[UE4SSMod],
    save_enabled: bool,
    save_json: bool,
    save_txt: bool,
) -> Result<(), ModError> {
    let mods_folder = mods_folder.as_ref();

    if save_enabled {
        for m in mods {
            let mod_path = Path::new(&m.path);
            let enabled_file = mod_path.join("enabled.txt");
            if m.enabled {
                fs::write(enabled_file, "")?;
            } else if enabled_file.exists() {
                fs::remove_file(enabled_file)?;
            }
        }
    }

    if save_json {
        let enabled_mods: Vec<serde_json::Value> = mods
            .iter()
            .filter(|m| m.enabled)
            .map(|m| {
                serde_json::json!({
                    "mod_name": m.name,
                    "mod_enabled": true
                })
            })
            .collect();

        let json_path = mods_folder.join("mods.json");
        let json_str = serde_json::to_string_pretty(&enabled_mods)?;
        fs::write(json_path, json_str)?;
    }

    if save_txt {
        let mut txt_content = String::new();
        for m in mods {
            if m.enabled {
                txt_content.push_str(&format!("{} : 1\r\n", m.name));
            }
        }

        let txt_path = mods_folder.join("mods.txt");
        fs::write(txt_path, txt_content)?;
    }

    Ok(())
}

pub fn launch_game<P: AsRef<Path>>(mods_folder: P) -> Result<String, ModError> {
    let start_dir = mods_folder.as_ref();

    for search_dir in candidate_game_search_dirs(start_dir) {
        if let Some(dir) = search_dir {
            let mut matches = find_game_launch_candidates(dir);

            if !matches.is_empty() {
                matches.sort_by(|a, b| {
                    let a_name = a.file_name().unwrap().to_ascii_lowercase();
                    let b_name = b.file_name().unwrap().to_ascii_lowercase();
                    launch_candidate_priority(a)
                        .cmp(&launch_candidate_priority(b))
                        .then_with(|| a_name.cmp(&b_name))
                });
                let game_exe = &matches[0];

                launch_game_path(game_exe)?;

                return Ok(game_exe.file_name().unwrap().to_string_lossy().to_string());
            }
        }
    }

    Err(ModError::GameExecutableNotFound)
}

fn candidate_game_search_dirs(start_dir: &Path) -> Vec<Option<&Path>> {
    vec![
        start_dir.parent(),
        start_dir.parent().and_then(|p| p.parent()),
        start_dir
            .parent()
            .and_then(|p| p.parent())
            .and_then(|p| p.parent()),
    ]
}

fn find_game_launch_candidates(search_dir: &Path) -> Vec<PathBuf> {
    let mut matches = Vec::new();

    for entry in walkdir::WalkDir::new(search_dir)
        .max_depth(4)
        .into_iter()
        .filter_map(Result::ok)
    {
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|n| n.to_str()) else {
            continue;
        };

        if is_game_launch_candidate(path, name) {
            matches.push(path.to_path_buf());
        }
    }

    matches
}

fn launch_candidate_priority(_path: &Path) -> u8 {
    #[cfg(target_os = "linux")]
    {
        let Some(name) = _path.file_name().and_then(|n| n.to_str()) else {
            return u8::MAX;
        };

        if name.ends_with("Linux-Shipping") {
            return 0;
        }
        if name.ends_with("Linux-Shipping.exe") {
            return 1;
        }
        if name.ends_with("Win64-Shipping.exe") || name.ends_with("WinGDK-Shipping.exe") {
            return 10;
        }
    }

    #[cfg(target_os = "macos")]
    {
        let Some(name) = _path.file_name().and_then(|n| n.to_str()) else {
            return u8::MAX;
        };

        if _path.is_dir() && name.ends_with(".app") {
            return 0;
        }
        if name.ends_with("Mac-Shipping") {
            return 1;
        }
    }

    0
}

fn is_game_launch_candidate(path: &Path, name: &str) -> bool {
    #[cfg(target_os = "windows")]
    {
        path.is_file()
            && (name.ends_with("Win64-Shipping.exe") || name.ends_with("WinGDK-Shipping.exe"))
    }

    #[cfg(target_os = "linux")]
    {
        path.is_file()
            && (name.ends_with("Linux-Shipping")
                || name.ends_with("Linux-Shipping.exe")
                || name.ends_with("Win64-Shipping.exe")
                || name.ends_with("WinGDK-Shipping.exe"))
    }

    #[cfg(target_os = "macos")]
    {
        (path.is_dir() && name.ends_with(".app"))
            || (path.is_file() && name.ends_with("Mac-Shipping"))
    }

    #[cfg(not(any(target_os = "windows", target_os = "linux", target_os = "macos")))]
    {
        path.is_file() && name.contains("Shipping")
    }
}

fn launch_game_path(game_path: &Path) -> Result<(), ModError> {
    #[cfg(target_os = "macos")]
    {
        if game_path.extension().and_then(|e| e.to_str()) == Some("app") {
            Command::new("open")
                .arg(game_path)
                .spawn()
                .map_err(|e| ModError::GameLaunchFailed(e.to_string()))?;
            return Ok(());
        }
    }

    Command::new(game_path)
        .current_dir(game_path.parent().unwrap_or_else(|| Path::new(".")))
        .spawn()
        .map_err(|e| ModError::GameLaunchFailed(e.to_string()))?;

    Ok(())
}

fn copy_dir_all(src: impl AsRef<Path>, dst: impl AsRef<Path>) -> std::io::Result<()> {
    fs::create_dir_all(&dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let ty = entry.file_type()?;
        if ty.is_dir() {
            copy_dir_all(entry.path(), dst.as_ref().join(entry.file_name()))?;
        } else {
            fs::copy(entry.path(), dst.as_ref().join(entry.file_name()))?;
        }
    }
    Ok(())
}

fn get_config_path() -> Option<PathBuf> {
    let mut config_dir = platform_config_dir()?;
    config_dir.push("UE4SS Mod Manager");
    if fs::create_dir_all(&config_dir).is_err() {
        return None;
    }
    Some(config_dir.join("manager_config.json"))
}

#[cfg(target_os = "windows")]
fn platform_config_dir() -> Option<PathBuf> {
    std::env::var_os("APPDATA").map(PathBuf::from)
}

#[cfg(target_os = "macos")]
fn platform_config_dir() -> Option<PathBuf> {
    std::env::var_os("HOME")
        .map(PathBuf::from)
        .map(|home| home.join("Library").join("Application Support"))
}

#[cfg(all(unix, not(target_os = "macos")))]
fn platform_config_dir() -> Option<PathBuf> {
    std::env::var_os("XDG_CONFIG_HOME")
        .map(PathBuf::from)
        .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".config")))
}

#[cfg(not(any(windows, unix)))]
fn platform_config_dir() -> Option<PathBuf> {
    std::env::current_dir().ok()
}

pub fn load_app_config() -> crate::mod_manager::models::AppConfig {
    use crate::mod_manager::models::AppConfig;

    let path = match get_config_path() {
        Some(p) => p,
        None => return AppConfig::default(),
    };

    if !path.exists() {
        let mut config = AppConfig::default();
        if let Some(detected) = detect_mods_folder() {
            config.mods_folder = Some(detected.to_string_lossy().to_string());
            let _ = save_app_config(&config);
        }
        return config;
    }

    match fs::File::open(&path) {
        Ok(file) => {
            let reader = std::io::BufReader::new(file);
            serde_json::from_reader(reader).unwrap_or_else(|_| {
                let mut config = AppConfig::default();
                if let Some(detected) = detect_mods_folder() {
                    config.mods_folder = Some(detected.to_string_lossy().to_string());
                    let _ = save_app_config(&config);
                }
                config
            })
        }
        Err(_) => AppConfig::default(),
    }
}

pub fn save_app_config(config: &crate::mod_manager::models::AppConfig) -> Result<(), ModError> {
    let path = get_config_path().ok_or_else(|| {
        ModError::Io(std::io::Error::new(
            std::io::ErrorKind::NotFound,
            "Could not determine executable path",
        ))
    })?;

    let file = fs::File::create(path)?;
    let writer = std::io::BufWriter::new(file);
    serde_json::to_writer_pretty(writer, config)?;
    Ok(())
}

pub fn uninstall_mod<P: AsRef<Path>>(mods_folder: P, mod_name: &str) -> Result<(), ModError> {
    let mods_folder = mods_folder.as_ref();
    let mod_path = mods_folder.join(mod_name);

    if !mod_path.exists() {
        return Ok(());
    }

    // Security check: Refuse to remove paths outside of the managed mods folder
    let canonical_folder = mods_folder.canonicalize()?;
    let canonical_mod = mod_path.canonicalize()?;
    if !canonical_mod.starts_with(&canonical_folder) || canonical_mod == canonical_folder {
        return Err(ModError::InvalidMod(format!(
            "Refusing to remove path outside managed mods directory: {}",
            mod_path.display()
        )));
    }

    fs::remove_dir_all(&mod_path)?;
    Ok(())
}

fn get_ue4ss_settings_path(mods_folder: &Path) -> Result<PathBuf, ModError> {
    // 1. Check mods_folder.parent()/UE4SS-settings.ini
    if let Some(parent) = mods_folder.parent() {
        let path = parent.join("UE4SS-settings.ini");
        if path.is_file() {
            return Ok(path);
        }
    }

    // 2. Check if it's directly inside mods_folder (sometimes people put it there, though rare)
    let path = mods_folder.join("UE4SS-settings.ini");
    if path.is_file() {
        return Ok(path);
    }

    // 3. Fallback: return not found error
    Err(ModError::InvalidMod("UE4SS-settings.ini not found in parent directory of Mods. Please ensure UE4SS is installed correctly.".to_string()))
}

pub fn load_ue4ss_settings<P: AsRef<Path>>(
    mods_folder: P,
) -> Result<Vec<crate::mod_manager::models::Ue4ssSettingsEntry>, ModError> {
    let mods_folder = mods_folder.as_ref();
    let settings_path = get_ue4ss_settings_path(mods_folder)?;
    let doc = super::ini_parser::IniDocument::from_path(settings_path)?;
    Ok(doc.get_entries())
}

pub fn save_ue4ss_settings<P: AsRef<Path>>(
    mods_folder: P,
    updates: std::collections::HashMap<String, String>,
) -> Result<(), ModError> {
    let mods_folder = mods_folder.as_ref();
    let settings_path = get_ue4ss_settings_path(mods_folder)?;
    let doc = super::ini_parser::IniDocument::from_path(settings_path)?;
    doc.save(&updates)
}
