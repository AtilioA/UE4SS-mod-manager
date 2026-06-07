use thiserror::Error;

#[derive(Debug, Error)]
pub enum ModError {
    #[error("I/O Error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Zip Error: {0}")]
    Zip(#[from] zip::result::ZipError),

    #[error("JSON Error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Invalid Mod: {0}")]
    InvalidMod(String),

    #[error("Invalid Mods Folder: {0}")]
    InvalidModFolder(String),

    #[error("Mod '{0}' already exists.")]
    ModAlreadyExists(String),

    #[error("Config Validation Error: {0}")]
    ConfigValidation(String),

    #[error("Game executable not found. Searched nearby folders for platform launch targets such as Win64-Shipping.exe, WinGDK-Shipping.exe, Linux-Shipping, Mac-Shipping, or a macOS .app bundle.")]
    GameExecutableNotFound,

    #[error("Failed to launch game: {0}")]
    GameLaunchFailed(String),
}

// Convert errors to String serialization so they pass seamlessly across Tauri's IPC bridge
impl serde::Serialize for ModError {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: serde::Serializer,
    {
        serializer.serialize_str(&self.to_string())
    }
}
