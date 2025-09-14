#!/bin/bash
# Quick Apple Unmatched Transaction Summary Script
#
# This script provides fast command-line summaries of unmatched Apple transactions
# using jq to parse the JSON results files.

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to find the latest results file
find_latest_results() {
    local results_dir="$(dirname "$0")/results"
    if [[ ! -d "$results_dir" ]]; then
        echo "Error: Results directory not found. Run the batch matcher first." >&2
        exit 1
    fi
    
    local latest_file=$(find "$results_dir" -name "*apple_matching_results.json" -type f -exec ls -t {} + | head -n1)
    if [[ -z "$latest_file" ]]; then
        echo "Error: No Apple matching results files found. Run the batch matcher first." >&2
        exit 1
    fi
    
    echo "$latest_file"
}

# Function to show basic summary
show_summary() {
    local file="$1"
    
    echo -e "${BLUE}=== APPLE UNMATCHED TRANSACTIONS SUMMARY ===${NC}"
    echo -e "${GREEN}Results file: $(basename "$file")${NC}"
    
    local date_range=$(jq -r '"\(.date_range.start) to \(.date_range.end)"' "$file")
    echo -e "${GREEN}Date range: $date_range${NC}"
    
    local total=$(jq '.results | length' "$file")
    local matched=$(jq '[.results[] | select(.matched == true)] | length' "$file")
    local unmatched=$(jq '[.results[] | select(.matched == false)] | length' "$file")
    local match_rate=$(jq '.summary.match_rate * 100' "$file")
    
    echo -e "${GREEN}Total transactions: $total${NC}"
    echo -e "${GREEN}Matched: $matched${NC}"
    echo -e "${RED}Unmatched: $unmatched${NC}"
    echo -e "${GREEN}Match rate: $(printf "%.1f" "$match_rate")%${NC}"
    echo ""
}

# Function to show unmatched by payee
show_by_payee() {
    local file="$1"
    
    echo -e "${BLUE}=== UNMATCHED BY PAYEE ===${NC}"
    jq -r '.results[] | select(.matched == false) | .ynab_transaction.payee_name' "$file" | \
        sort | uniq -c | sort -nr | \
        while read count payee; do
            echo -e "${YELLOW}$count${NC} - $payee"
        done
    echo ""
}

# Function to show largest unmatched amounts
show_largest_amounts() {
    local file="$1"
    local limit="${2:-10}"
    
    echo -e "${BLUE}=== TOP $limit UNMATCHED BY AMOUNT ===${NC}"
    jq -r --arg limit "$limit" '.results[] | select(.matched == false) | 
        "\(.ynab_transaction.amount)|\(.ynab_transaction.payee_name)|\(.ynab_transaction.date)"' "$file" | \
        sort -t'|' -k1,1nr | head -n "$limit" | \
        while IFS='|' read amount payee date; do
            printf "${RED}%8.2f${NC} - %-30s - %s\n" "$amount" "$payee" "$date"
        done
    echo ""
}

# Function to show unmatched by date range
show_by_month() {
    local file="$1"
    
    echo -e "${BLUE}=== UNMATCHED BY MONTH ===${NC}"
    jq -r '.results[] | select(.matched == false) | .ynab_transaction.date' "$file" | \
        cut -d'-' -f1,2 | sort | uniq -c | \
        while read count month; do
            echo -e "${YELLOW}$count${NC} - $month"
        done
    echo ""
}

# Function to show category breakdown
show_categories() {
    local file="$1"
    
    echo -e "${BLUE}=== UNMATCHED BY CATEGORY ===${NC}"
    
    local services=$(jq '[.results[] | select(.matched == false and .ynab_transaction.payee_name == "Apple Services")] | length' "$file")
    local icloud=$(jq '[.results[] | select(.matched == false and (.ynab_transaction.payee_name | contains("APPLE.COM/BILL")))] | length' "$file")
    local store=$(jq '[.results[] | select(.matched == false and (.ynab_transaction.payee_name | contains("Apple Store")))] | length' "$file")
    local other=$(jq --argjson services "$services" --argjson icloud "$icloud" --argjson store "$store" \
        '[.results[] | select(.matched == false)] | length - $services - $icloud - $store' "$file")
    
    echo -e "${YELLOW}$services${NC} - Apple Services (subscriptions)"
    echo -e "${YELLOW}$icloud${NC} - APPLE.COM/BILL (iCloud/subscriptions)"
    echo -e "${YELLOW}$store${NC} - Apple Store (hardware)"
    echo -e "${YELLOW}$other${NC} - Other Apple transactions"
    echo ""
}

# Function to export unmatched to CSV
export_csv() {
    local file="$1"
    local output="${2:-unmatched_apple_transactions.csv}"
    
    echo -e "${BLUE}=== EXPORTING TO CSV ===${NC}"
    
    # Create CSV header
    echo "id,date,amount,payee_name,account_name,reason" > "$output"
    
    # Export data
    jq -r '.results[] | select(.matched == false) | 
        [.ynab_transaction.id, .ynab_transaction.date, .ynab_transaction.amount, 
         .ynab_transaction.payee_name, .ynab_transaction.account_name, 
         (.match_details.reason // "no_matching_receipts_found")] | @csv' "$file" >> "$output"
    
    local count=$(tail -n +2 "$output" | wc -l)
    echo -e "${GREEN}Exported $count unmatched transactions to: $output${NC}"
    echo ""
}

# Function to show specific category details
show_category_details() {
    local file="$1"
    local category="$2"
    local limit="${3:-20}"
    
    case "$category" in
        "services")
            echo -e "${BLUE}=== APPLE SERVICES TRANSACTIONS ===${NC}"
            jq -r --arg limit "$limit" '.results[] | 
                select(.matched == false and .ynab_transaction.payee_name == "Apple Services") | 
                "\(.ynab_transaction.amount)|\(.ynab_transaction.date)|\(.ynab_transaction.account_name)"' "$file" | \
                sort -t'|' -k1,1nr | head -n "$limit" | \
                while IFS='|' read amount date account; do
                    printf "${RED}%8.2f${NC} - %s - %s\n" "$amount" "$date" "$account"
                done
            ;;
        "icloud")
            echo -e "${BLUE}=== APPLE.COM/BILL TRANSACTIONS ===${NC}"
            jq -r --arg limit "$limit" '.results[] | 
                select(.matched == false and (.ynab_transaction.payee_name | contains("APPLE.COM/BILL"))) | 
                "\(.ynab_transaction.amount)|\(.ynab_transaction.date)|\(.ynab_transaction.account_name)"' "$file" | \
                sort -t'|' -k1,1nr | head -n "$limit" | \
                while IFS='|' read amount date account; do
                    printf "${RED}%8.2f${NC} - %s - %s\n" "$amount" "$date" "$account"
                done
            ;;
        "store")
            echo -e "${BLUE}=== APPLE STORE TRANSACTIONS ===${NC}"
            jq -r --arg limit "$limit" '.results[] | 
                select(.matched == false and (.ynab_transaction.payee_name | contains("Apple Store"))) | 
                "\(.ynab_transaction.amount)|\(.ynab_transaction.date)|\(.ynab_transaction.payee_name)"' "$file" | \
                sort -t'|' -k1,1nr | head -n "$limit" | \
                while IFS='|' read amount date payee; do
                    printf "${RED}%8.2f${NC} - %s - %s\n" "$amount" "$date" "$payee"
                done
            ;;
        *)
            echo "Error: Unknown category '$category'. Use: services, icloud, or store" >&2
            exit 1
            ;;
    esac
    echo ""
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [RESULTS_FILE]"
    echo ""
    echo "Quick summary of unmatched Apple transactions from matching results."
    echo ""
    echo "Options:"
    echo "  -h, --help              Show this help message"
    echo "  -s, --summary           Show basic summary (default)"
    echo "  -p, --payee             Show breakdown by payee"
    echo "  -a, --amounts [N]       Show top N largest amounts (default: 10)"
    echo "  -m, --monthly           Show breakdown by month"
    echo "  -c, --categories        Show breakdown by category"
    echo "  -d, --details CATEGORY  Show details for category (services|icloud|store)"
    echo "  -e, --export [FILE]     Export to CSV (default: unmatched_apple_transactions.csv)"
    echo ""
    echo "Examples:"
    echo "  $0                      # Show basic summary of latest results"
    echo "  $0 --payee             # Show breakdown by payee"
    echo "  $0 --amounts 20        # Show top 20 largest unmatched amounts"
    echo "  $0 --details services  # Show Apple Services subscription details"
    echo "  $0 --export my_file.csv # Export to custom CSV file"
    echo ""
}

# Main script logic
main() {
    local file=""
    local show_help=false
    local show_basic=true
    local show_payees=false
    local show_amounts=false
    local amounts_limit=10
    local show_monthly=false
    local show_cats=false
    local category_details=""
    local export_file=""
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                show_help=true
                shift
                ;;
            -s|--summary)
                show_basic=true
                shift
                ;;
            -p|--payee)
                show_payees=true
                show_basic=false
                shift
                ;;
            -a|--amounts)
                show_amounts=true
                show_basic=false
                if [[ $2 =~ ^[0-9]+$ ]]; then
                    amounts_limit="$2"
                    shift
                fi
                shift
                ;;
            -m|--monthly)
                show_monthly=true
                show_basic=false
                shift
                ;;
            -c|--categories)
                show_cats=true
                show_basic=false
                shift
                ;;
            -d|--details)
                category_details="$2"
                show_basic=false
                shift 2
                ;;
            -e|--export)
                if [[ $2 && ! $2 =~ ^- ]]; then
                    export_file="$2"
                    shift
                else
                    export_file="unmatched_apple_transactions.csv"
                fi
                show_basic=false
                shift
                ;;
            -*)
                echo "Error: Unknown option '$1'" >&2
                show_usage
                exit 1
                ;;
            *)
                if [[ -z "$file" ]]; then
                    file="$1"
                else
                    echo "Error: Multiple files specified" >&2
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    if $show_help; then
        show_usage
        exit 0
    fi
    
    # Determine which file to use
    if [[ -z "$file" ]]; then
        file=$(find_latest_results)
        echo -e "${GREEN}Using latest results file: $(basename "$file")${NC}"
    elif [[ ! -f "$file" ]]; then
        echo "Error: Results file not found: $file" >&2
        exit 1
    fi
    
    # Validate jq is available
    if ! command -v jq >/dev/null 2>&1; then
        echo "Error: jq is required but not installed." >&2
        echo "Install with: brew install jq" >&2
        exit 1
    fi
    
    # Show requested information
    if $show_basic; then
        show_summary "$file"
        show_categories "$file"
    fi
    
    if $show_payees; then
        show_summary "$file"
        show_by_payee "$file"
    fi
    
    if $show_amounts; then
        show_summary "$file"
        show_largest_amounts "$file" "$amounts_limit"
    fi
    
    if $show_monthly; then
        show_summary "$file"
        show_by_month "$file"
    fi
    
    if $show_cats; then
        show_summary "$file"
        show_categories "$file"
    fi
    
    if [[ -n "$category_details" ]]; then
        show_summary "$file"
        show_category_details "$file" "$category_details"
    fi
    
    if [[ -n "$export_file" ]]; then
        show_summary "$file"
        export_csv "$file" "$export_file"
    fi
}

# Run main function with all arguments
main "$@"