use crate::error::ModError;
use crate::mod_manager::models::Ue4ssSettingsEntry;
use std::collections::HashMap;
use std::fs;
use std::io::{self, BufRead};
use std::path::{Path, PathBuf};

pub struct IniDocument {
    pub filepath: PathBuf,
    pub lines: Vec<String>,
}

impl IniDocument {
    pub fn from_path<P: AsRef<Path>>(path: P) -> Result<Self, ModError> {
        let path = path.as_ref();
        if !path.exists() {
            return Err(ModError::Io(io::Error::new(
                io::ErrorKind::NotFound,
                format!("INI file not found: {}", path.display()),
            )));
        }

        let file = fs::File::open(path)?;
        let reader = io::BufReader::new(file);
        let mut lines = Vec::new();

        for line_res in reader.lines() {
            lines.push(line_res?);
        }

        Ok(Self {
            filepath: path.to_path_buf(),
            lines,
        })
    }

    pub fn get_entries(&self) -> Vec<Ue4ssSettingsEntry> {
        let mut entries = Vec::new();
        let mut current_section = "General".to_string();
        let mut accumulated_comments = Vec::new();

        for line in &self.lines {
            let trimmed = line.trim();

            // Skip empty lines and reset comment accumulator
            if trimmed.is_empty() {
                accumulated_comments.clear();
                continue;
            }

            // Check for section header
            if trimmed.starts_with('[') && trimmed.ends_with(']') {
                let section_name = trimmed[1..trimmed.len() - 1].trim();
                current_section = section_name.to_string();
                accumulated_comments.clear();
                continue;
            }

            // Check for comments
            if trimmed.starts_with(';') || trimmed.starts_with('#') {
                // Strip the comment prefix and trim
                let clean_comment = trimmed[1..].trim();
                if !clean_comment.is_empty() {
                    accumulated_comments.push(clean_comment.to_string());
                }
                continue;
            }

            // Check for key-value pair
            if let Some(equals_idx) = trimmed.find('=') {
                let raw_key = trimmed[..equals_idx].trim();
                let raw_value_part = trimmed[equals_idx + 1..].trim();

                if raw_key.is_empty() {
                    accumulated_comments.clear();
                    continue;
                }

                // Strip inline trailing comments from value
                let mut value = raw_value_part.to_string();
                if let Some(comment_idx) = raw_value_part.find(';') {
                    value = raw_value_part[..comment_idx].trim().to_string();
                } else if let Some(comment_idx) = raw_value_part.find('#') {
                    value = raw_value_part[..comment_idx].trim().to_string();
                }

                let comment = accumulated_comments.join("\n");
                accumulated_comments.clear();

                entries.push(Ue4ssSettingsEntry {
                    section: current_section.clone(),
                    key: raw_key.to_string(),
                    value,
                    comment,
                });
            } else {
                // If it's not a key-value or comment, clear the accumulator
                accumulated_comments.clear();
            }
        }

        entries
    }

    pub fn save(&self, updates: &HashMap<String, String>) -> Result<(), ModError> {
        let mut new_lines = Vec::new();
        let mut current_section = "General".to_string();

        for line in &self.lines {
            let trimmed = line.trim();

            // Track sections
            if trimmed.starts_with('[') && trimmed.ends_with(']') {
                current_section = trimmed[1..trimmed.len() - 1].trim().to_string();
                new_lines.push(line.clone());
                continue;
            }

            // Try to match key-value line
            if let Some(equals_idx) = line.find('=') {
                let key_part = &line[..equals_idx];
                let key_trimmed = key_part.trim();

                // Build unique section keys or pure key check
                let section_key = format!("{}/{}", current_section, key_trimmed);
                let update_val = updates
                    .get(&section_key)
                    .or_else(|| updates.get(key_trimmed));

                if let Some(new_value) = update_val {
                    // Extract trailing inline comment and value before it
                    let value_part = &line[equals_idx + 1..];

                    let mut comment_idx = value_part.len();
                    let mut inline_comment = "";
                    if let Some(idx) = value_part.find(';') {
                        comment_idx = idx;
                        inline_comment = &value_part[idx..];
                    } else if let Some(idx) = value_part.find('#') {
                        comment_idx = idx;
                        inline_comment = &value_part[idx..];
                    }

                    let val_before_comment = &value_part[..comment_idx];
                    let val_trimmed = val_before_comment.trim();

                    let (start_spaces, end_spaces) = if val_trimmed.is_empty() {
                        (" ", "")
                    } else {
                        let start_space_len =
                            val_before_comment.len() - val_before_comment.trim_start().len();
                        let end_space_len =
                            val_before_comment.len() - val_before_comment.trim_end().len();
                        (
                            &val_before_comment[..start_space_len],
                            &val_before_comment[val_before_comment.len() - end_space_len..],
                        )
                    };

                    // Rebuild keeping original key-part spacing & trailing comments
                    let rebuilt_line = format!(
                        "{}={}{}{}{}",
                        key_part, start_spaces, new_value, end_spaces, inline_comment
                    );
                    new_lines.push(rebuilt_line);
                } else {
                    new_lines.push(line.clone());
                }
            } else {
                new_lines.push(line.clone());
            }
        }

        fs::write(&self.filepath, new_lines.join("\n") + "\n")?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_ini_parsing_and_saving() {
        let dir = tempdir().unwrap();
        let file_path = dir.path().join("UE4SS-settings.ini");

        let initial_content = r#"
[Settings]
; Enable the debug console
ConsoleEnabled = 0
GuiConsoleEnabled = 0

[Debug]
; Enable debug overlays
; Another line of comment
EnableOverlay = 0 ; inline comment here
"#;

        fs::write(&file_path, initial_content).unwrap();

        let doc = IniDocument::from_path(&file_path).unwrap();
        let entries = doc.get_entries();

        assert_eq!(entries.len(), 3);
        assert_eq!(entries[0].section, "Settings");
        assert_eq!(entries[0].key, "ConsoleEnabled");
        assert_eq!(entries[0].value, "0");
        assert_eq!(entries[0].comment, "Enable the debug console");

        assert_eq!(entries[2].section, "Debug");
        assert_eq!(entries[2].key, "EnableOverlay");
        assert_eq!(entries[2].value, "0");
        assert_eq!(
            entries[2].comment,
            "Enable debug overlays\nAnother line of comment"
        );

        // Save updates
        let mut updates = HashMap::new();
        updates.insert("Settings/ConsoleEnabled".to_string(), "1".to_string());
        updates.insert("EnableOverlay".to_string(), "1".to_string());

        doc.save(&updates).unwrap();

        let updated_content = fs::read_to_string(&file_path).unwrap();
        assert!(updated_content.contains("ConsoleEnabled = 1"));
        assert!(updated_content.contains("EnableOverlay = 1 ; inline comment here"));
    }
}
