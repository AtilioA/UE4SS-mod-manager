use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use regex::Regex;
use crate::error::ModError;
use crate::mod_manager::models::LuaConfigEntry;

#[derive(Debug, Clone)]
struct ParsedLuaEntry {
    key: String,
    value: serde_json::Value,
    value_type: String, // "boolean" | "number" | "string" | "nil"
    line_index: usize,
    value_start: usize,
    value_end: usize,
    quote: char,
    comment: String,
}

pub struct LuaConfigDocument {
    path: PathBuf,
    lines: Vec<String>,
    entries: Vec<ParsedLuaEntry>,
}

impl LuaConfigDocument {
    pub fn from_path<P: AsRef<Path>>(path: P) -> Result<Self, ModError> {
        let path_buf = path.as_ref().to_path_buf();
        let content = fs::read_to_string(&path_buf)?;
        Ok(Self::from_text(&content, path_buf))
    }

    pub fn from_text(text: &str, path: PathBuf) -> Self {
        // split_inclusive keeps the trailing \n or \r\n characters
        let lines: Vec<String> = text.split_inclusive('\n').map(|s| s.to_string()).collect();
        let mut entries = Vec::new();
        let mut seen_keys = std::collections::HashSet::new();
        let mut pending_comments = Vec::new();
        let mut table_depth = 0;

        let re_assignment = Regex::new(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*=\s*)").unwrap();

        for (line_index, line) in lines.iter().enumerate() {
            if table_depth == 1 {
                if let Some(comment) = parse_comment_line(line) {
                    pending_comments.push(comment);
                } else if let Some(parsed) = parse_line(line, line_index, &pending_comments.join("\n"), &re_assignment) {
                    if !seen_keys.contains(&parsed.key) {
                        seen_keys.insert(parsed.key.clone());
                        entries.push(parsed);
                    }
                    pending_comments.clear();
                } else {
                    pending_comments.clear();
                }
            } else {
                pending_comments.clear();
            }

            table_depth += table_depth_delta(line);
            if table_depth < 0 {
                table_depth = 0;
            }
        }

        Self {
            path,
            lines,
            entries,
        }
    }

    pub fn get_entries(&self) -> Vec<LuaConfigEntry> {
        self.entries
            .iter()
            .map(|e| LuaConfigEntry {
                key: e.key.clone(),
                value: e.value.clone(),
                value_type: e.value_type.clone(),
                comment: e.comment.clone(),
            })
            .collect()
    }

    pub fn save(&mut self, updates: &HashMap<String, serde_json::Value>) -> Result<(), ModError> {
        let mut updated_lines = self.lines.clone();

        for entry in self.entries.iter().rev() {
            if let Some(new_value) = updates.get(&entry.key) {
                let formatted = format_lua_value(new_value, &entry.value_type, entry.quote)?;
                let line = &updated_lines[entry.line_index];

                // Perform replacement on a Vector of chars to prevent UTF-8 indexing and slicing panics
                let chars: Vec<char> = line.chars().collect();
                let prefix: String = chars[..entry.value_start].iter().collect();
                let suffix: String = chars[entry.value_end..].iter().collect();

                updated_lines[entry.line_index] = format!("{}{}{}", prefix, formatted, suffix);
            }
        }

        // Write the modifications back to disk using UTF-8
        let full_output = updated_lines.concat();
        fs::write(&self.path, full_output)?;
        Ok(())
    }
}

fn parse_line(
    line: &str,
    line_index: usize,
    comment: &str,
    re_assignment: &Regex,
) -> Option<ParsedLuaEntry> {
    let stripped = line.trim_start();
    if stripped.starts_with("--") || stripped.starts_with("return") || stripped.starts_with('}') {
        return None;
    }

    if let Some(captures) = re_assignment.captures(line) {
        let matched_prefix_end = captures.get(0).unwrap().end();
        let key = captures.get(2).unwrap().as_str().to_string();

        if let Some((start, end, quote)) = read_value_token(line, matched_prefix_end) {
            let line_chars: Vec<char> = line.chars().collect();
            let token: String = line_chars[start..end].iter().collect();

            if let Some((value, value_type)) = parse_value_token(&token, quote) {
                return Some(ParsedLuaEntry {
                    key,
                    value,
                    value_type,
                    line_index,
                    value_start: start,
                    value_end: end,
                    quote,
                    comment: comment.to_string(),
                });
            }
        }
    }

    None
}

fn parse_comment_line(line: &str) -> Option<String> {
    let stripped = line.trim();
    if !stripped.starts_with("--") {
        return None;
    }
    Some(stripped[2..].trim().to_string())
}

fn read_value_token(line: &str, start: usize) -> Option<(usize, usize, char)> {
    let line_without_newline = line.trim_end_matches(|c| c == '\r' || c == '\n');
    let chars: Vec<char> = line_without_newline.chars().collect();
    let mut index = start;

    while index < chars.len() && chars[index].is_whitespace() {
        index += 1;
    }

    if index >= chars.len() {
        return None;
    }

    let first_char = chars[index];
    if first_char == '\'' || first_char == '"' {
        let quote = first_char;
        let mut cursor = index + 1;
        let mut escaped = false;

        while cursor < chars.len() {
            let char = chars[cursor];
            if char == quote && !escaped {
                let end = cursor + 1;
                let trailer: String = chars[end..].iter().collect();
                if has_only_value_terminator(&trailer) {
                    return Some((index, end, quote));
                } else {
                    return None;
                }
            }
            escaped = char == '\\' && !escaped;
            if char != '\\' {
                escaped = false;
            }
            cursor += 1;
        }
        return None;
    }

    let mut cursor = index;
    while cursor < chars.len() {
        let current_char = chars[cursor];
        let trailer: String = chars[cursor..].iter().collect();

        if current_char == ',' || trailer.starts_with("--") || current_char.is_whitespace() {
            break;
        }
        cursor += 1;
    }

    let trailer: String = chars[cursor..].iter().collect();
    if has_only_value_terminator(&trailer) {
        Some((index, cursor, '"'))
    } else {
        None
    }
}

fn has_only_value_terminator(trailer: &str) -> bool {
    let trailer = trailer.trim();
    if trailer.is_empty() {
        return true;
    }
    if trailer.starts_with("--") {
        return true;
    }
    if trailer.starts_with(',') {
        let after_comma = trailer[1..].trim();
        return after_comma.is_empty() || after_comma.starts_with("--");
    }
    false
}

fn parse_value_token(token: &str, quote_char: char) -> Option<(serde_json::Value, String)> {
    let lowered = token.to_lowercase();
    if lowered == "true" {
        return Some((serde_json::Value::Bool(true), "boolean".to_string()));
    }
    if lowered == "false" {
        return Some((serde_json::Value::Bool(false), "boolean".to_string()));
    }
    if lowered == "nil" {
        return Some((serde_json::Value::Null, "nil".to_string()));
    }
    if token.len() >= 2 && (token.starts_with('\'') || token.starts_with('"')) && token.ends_with(token.chars().next().unwrap()) {
        let inner = &token[1..token.len() - 1];
        let unescaped = unescape_lua_string(inner, quote_char);
        return Some((serde_json::Value::String(unescaped), "string".to_string()));
    }

    // Number check using standard float regex
    let re_number = Regex::new(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$").unwrap();
    if re_number.is_match(token) {
        if let Ok(i) = token.parse::<i64>() {
            return Some((serde_json::Value::Number(serde_json::Number::from(i)), "number".to_string()));
        }
        if let Ok(f) = token.parse::<f64>() {
            if let Some(num) = serde_json::Number::from_f64(f) {
                return Some((serde_json::Value::Number(num), "number".to_string()));
            }
        }
        // Fallback if number parses strangely but is valid format
        return Some((serde_json::Value::String(token.to_string()), "number".to_string()));
    }

    None
}

fn unescape_lua_string(value: &str, quote: char) -> String {
    let mut output = String::new();
    let mut escaped = false;
    for char in value.chars() {
        if escaped {
            let unescaped_char = match char {
                'n' => '\n',
                'r' => '\r',
                't' => '\t',
                c if c == quote => quote,
                '\\' => '\\',
                c => c,
            };
            output.push(unescaped_char);
            escaped = false;
            continue;
        }
        if char == '\\' {
            escaped = true;
            continue;
        }
        output.push(char);
    }
    if escaped {
        output.push('\\');
    }
    output
}

fn table_depth_delta(line: &str) -> i32 {
    let mut delta = 0;
    let mut quote: Option<char> = None;
    let mut escaped = false;
    let chars: Vec<char> = line.chars().collect();
    let mut index = 0;

    while index < chars.len() {
        let char = chars[index];
        let remaining: String = chars[index..].iter().collect();

        if quote.is_none() && remaining.starts_with("--") {
            break;
        }

        if let Some(q) = quote {
            if char == q && !escaped {
                quote = None;
            }
            escaped = char == '\\' && !escaped;
            if char != '\\' {
                escaped = false;
            }
        } else if char == '\'' || char == '"' {
            quote = Some(char);
        } else if char == '{' {
            delta += 1;
        } else if char == '}' {
            delta -= 1;
        }

        index += 1;
    }

    delta
}

fn format_lua_value(value: &serde_json::Value, value_type: &str, quote: char) -> Result<String, ModError> {
    match value_type {
        "boolean" => {
            if let serde_json::Value::Bool(b) = value {
                Ok(if *b { "true".to_string() } else { "false".to_string() })
            } else {
                Err(ModError::ConfigValidation("Expected a boolean value.".to_string()))
            }
        }
        "number" => {
            if let serde_json::Value::Number(n) = value {
                Ok(n.to_string())
            } else if let serde_json::Value::String(s) = value {
                let re_number = Regex::new(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$").unwrap();
                if re_number.is_match(s) {
                    Ok(s.clone())
                } else {
                    Err(ModError::ConfigValidation("Expected a number, like 95, 95.0, or 1e3.".to_string()))
                }
            } else {
                Err(ModError::ConfigValidation("Expected a number value.".to_string()))
            }
        }
        "nil" => {
            if value.is_null() {
                Ok("nil".to_string())
            } else {
                Err(ModError::ConfigValidation("Expected nil.".to_string()))
            }
        }
        "string" => {
            if let serde_json::Value::String(s) = value {
                let escaped = s
                    .replace('\\', "\\\\")
                    .replace('\n', "\\n")
                    .replace('\r', "\\r")
                    .replace('\t', "\\t")
                    .replace(quote, &format!("\\{}", quote));
                Ok(format!("{}{}{}", quote, escaped, quote))
            } else {
                Err(ModError::ConfigValidation("Expected a string value.".to_string()))
            }
        }
        other => Err(ModError::ConfigValidation(format!("Unsupported config value type: {}", other))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use tempfile::tempdir;

    const CONFIG_TEXT: &str = "return {\n\tEnabled = true,\n\n\tTargetFOV = 95.0,\n\tName = \"Wide FOV\",\n\n\t-- F7 toggles the FOV reapply behavior on/off.\n\tEnableToggleHotkey = false, -- inline comment\n\tUnsupported = { Nested = true },\n}\n";

    #[test]
    fn test_parses_supported_top_level_values() {
        let path = PathBuf::from("config.lua");
        let doc = LuaConfigDocument::from_text(CONFIG_TEXT, path);
        let entries = doc.get_entries();
        let map: HashMap<String, LuaConfigEntry> = entries.into_iter().map(|e| (e.key.clone(), e)).collect();

        assert_eq!(map.get("Enabled").unwrap().value, serde_json::Value::Bool(true));
        assert_eq!(map.get("Enabled").unwrap().value_type, "boolean");

        assert_eq!(map.get("TargetFOV").unwrap().value.to_string(), "95.0");
        assert_eq!(map.get("TargetFOV").unwrap().value_type, "number");

        assert_eq!(map.get("Name").unwrap().value, serde_json::Value::String("Wide FOV".to_string()));
        assert_eq!(map.get("Name").unwrap().value_type, "string");

        assert_eq!(map.get("EnableToggleHotkey").unwrap().comment, "F7 toggles the FOV reapply behavior on/off.");
        assert!(!map.contains_key("Unsupported"));
    }

    #[test]
    fn test_nil_values_are_supported() {
        let dir = tempdir().unwrap();
        let config_path = dir.path().join("config.lua");
        fs::write(&config_path, "return {\n\tOptionalValue = nil,\n}\n").unwrap();

        let mut doc = LuaConfigDocument::from_path(&config_path).unwrap();
        let entries = doc.get_entries();
        assert_eq!(entries[0].key, "OptionalValue");
        assert_eq!(entries[0].value, serde_json::Value::Null);
        assert_eq!(entries[0].value_type, "nil");

        let mut updates = HashMap::new();
        updates.insert("OptionalValue".to_string(), serde_json::Value::Null);
        doc.save(&updates).unwrap();

        let content = fs::read_to_string(&config_path).unwrap();
        assert_eq!(content, "return {\n\tOptionalValue = nil,\n}\n");
    }

    #[test]
    fn test_multiline_contiguous_comments_are_used_as_label() {
        let text = "return {\n\t-- Reapply periodically because games can reset camera values after loading,\n\t-- entering vehicles, using tools, respawning, or rebuilding camera state.\n\tReapplyEveryMilliseconds = 5000,\n}\n";
        let doc = LuaConfigDocument::from_text(text, PathBuf::from("config.lua"));
        let entries = doc.get_entries();
        assert_eq!(
            entries[0].comment,
            "Reapply periodically because games can reset camera values after loading,\nentering vehicles, using tools, respawning, or rebuilding camera state."
        );
    }

    #[test]
    fn test_non_contiguous_comments_are_not_used_as_label() {
        let text = "return {\n\t-- This comment belongs to no setting.\n\n\tEnabled = true,\n}\n";
        let doc = LuaConfigDocument::from_text(text, PathBuf::from("config.lua"));
        let entries = doc.get_entries();
        assert!(entries[0].comment.is_empty());
    }

    #[test]
    fn test_save_replaces_only_supported_value_tokens() {
        let dir = tempdir().unwrap();
        let config_path = dir.path().join("config.lua");
        fs::write(&config_path, CONFIG_TEXT).unwrap();

        let mut doc = LuaConfigDocument::from_path(&config_path).unwrap();
        let mut updates = HashMap::new();
        updates.insert("Enabled".to_string(), serde_json::Value::Bool(false));
        updates.insert("TargetFOV".to_string(), serde_json::Value::String("100.5".to_string()));
        updates.insert("Name".to_string(), serde_json::Value::String("Narrow FOV".to_string()));

        doc.save(&updates).unwrap();

        let content = fs::read_to_string(&config_path).unwrap();
        let expected = "return {\n\tEnabled = false,\n\n\tTargetFOV = 100.5,\n\tName = \"Narrow FOV\",\n\n\t-- F7 toggles the FOV reapply behavior on/off.\n\tEnableToggleHotkey = false, -- inline comment\n\tUnsupported = { Nested = true },\n}\n";
        assert_eq!(content, expected);
    }

    #[test]
    fn test_nested_tables_and_expressions_are_ignored() {
        let text = "return {\n\tTopLevel = true,\n\tComputed = 1 + 2,\n\tNested = {\n\t\tEnabled = false,\n\t},\n}\n";
        let doc = LuaConfigDocument::from_text(text, PathBuf::from("config.lua"));
        let entries = doc.get_entries();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].key, "TopLevel");
    }

    #[test]
    fn test_partial_save_preserves_untouched_values_and_escapes_strings() {
        let dir = tempdir().unwrap();
        let config_path = dir.path().join("config.lua");
        let initial = "return {\n\tEnabled = true,\n\tName = 'Wide\\\\nFOV',\n\tPath = \"C:\\\\\\\\Mods\",\n}\n";
        fs::write(&config_path, initial).unwrap();

        let mut doc = LuaConfigDocument::from_path(&config_path).unwrap();
        let mut updates = HashMap::new();
        updates.insert("Name".to_string(), serde_json::Value::String("Narrow\nFOV".to_string()));

        doc.save(&updates).unwrap();

        let content = fs::read_to_string(&config_path).unwrap();
        let expected = "return {\n\tEnabled = true,\n\tName = 'Narrow\\nFOV',\n\tPath = \"C:\\\\\\\\Mods\",\n}\n";
        assert_eq!(content, expected);
    }

    #[test]
    fn test_duplicate_keys_only_expose_first_entry() {
        let text = "return {\n\tEnabled = true,\n\tEnabled = false,\n}\n";
        let doc = LuaConfigDocument::from_text(text, PathBuf::from("config.lua"));
        let entries = doc.get_entries();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].value, serde_json::Value::Bool(true));
    }
}

