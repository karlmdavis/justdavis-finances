#!/usr/bin/env /opt/homebrew/bin/nu

# Generic CSV/file opener with nushell pipeline support
# Usage: ./open.nu <file_path> [pipeline_commands...]
#
# Examples:
#   ./open.nu data.csv
#   ./open.nu data.csv "where name == 'foo'"
#   ./open.nu data.csv "where amount > 100 | sort-by amount"
#   ./open.nu data.csv "group-by category | each { |item| { name: $item.name, count: ($item.group | length) } }"

def main [file_path: string, ...pipeline_args] {
    if not ($file_path | path exists) {
        error make { msg: $"File not found: ($file_path)" }
    }
    
    let pipeline_str = ($pipeline_args | str join " ")
    
    if ($pipeline_str | is-empty) {
        # Just open the file
        open $file_path
    } else {
        # Build and execute the full pipeline
        let full_command = $"open \"($file_path)\" | ($pipeline_str)"
        nu -c $full_command
    }
}