use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
pub struct UE4SSMod {
    pub name: String,
    pub path: String,
    pub enabled: bool,
    pub scripts: Vec<String>,
    pub is_native: bool,
    pub lang: String, // "lua" | "cpp"
    pub config_path: Option<String>,
    pub conflicts: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
pub struct LuaConfigEntry {
    pub key: String,
    pub value: serde_json::Value, // Can be Bool, String, Number, or Null
    pub value_type: String,       // "boolean" | "number" | "string" | "nil"
    pub comment: String,
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
pub struct AppConfig {
    pub mods_folder: Option<String>,
    pub show_native: bool,
    pub save_enabled: bool,
    pub save_json: bool,
    pub save_txt: bool,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            mods_folder: None,
            show_native: false,
            save_enabled: true,
            save_json: false,
            save_txt: false,
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, PartialEq, Eq)]
pub struct Ue4ssSettingsEntry {
    pub section: String,
    pub key: String,
    pub value: String, // Keep as string; frontend can render appropriate inputs
    pub comment: String,
}
