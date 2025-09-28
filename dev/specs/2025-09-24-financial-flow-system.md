# Financial Flow System - Product Specification

## Executive Summary

The Financial Flow System provides intelligent, dependency-driven orchestration of all financial data
  operations in the Davis Family Finances ecosystem.
It automatically manages the complete data pipeline from source ingestion through YNAB updates,
  ensuring data consistency, minimizing manual intervention, and providing comprehensive audit trails.
The system employs a directed acyclic graph (DAG) to manage dependencies between operations,
  executing them in optimal order while detecting changes and archiving results transactionally.

## Problem Statement

### Current Pain Points

1. **Manual Command Orchestration**: Users must remember and execute 6-10 commands in precise order
   for complete financial data updates
2. **Dependency Management**: No automatic tracking of which operations need re-running when upstream
   data changes
3. **Partial Failure Recovery**: Mid-pipeline failures can leave data in inconsistent states across
   different domains
4. **Repetitive Configuration**: Each command requires similar parameters that must be manually
   synchronized
5. **Change Detection Overhead**: Users must manually check for new data in multiple sources
   (YNAB API, Amazon dumps, Apple emails)
6. **Archive Management**: No systematic approach to preserving historical outputs before regeneration
7. **Review Friction**: Multiple review points across different commands create workflow interruptions

### Business Impact

- **Time Investment**: 15-30 minutes of manual orchestration for each financial update cycle
- **Error Risk**: Manual sequencing increases chance of missed steps or incorrect ordering
- **Data Inconsistency**: Partial runs can create mismatched data between Amazon, Apple, and YNAB
  domains
- **Cognitive Load**: Users must maintain mental model of entire dependency chain
- **Delayed Updates**: Friction in running commands leads to less frequent financial data updates
- **Lost History**: Previous outputs overwritten without systematic archiving

## Success Criteria

### Primary Goals

1. **Single Command Execution**: One command triggers entire financial data update pipeline
2. **Intelligent Dependency Management**: Automatic detection and execution of required operations
3. **Transactional Consistency**: All-or-nothing execution with comprehensive archiving
4. **Unified Configuration**: Harmonized parameters across all operations
5. **Change Detection**: Automatic identification of new data requiring processing

### Measurable Outcomes

- **Command Reduction**: From 10+ manual commands to 1 flow command
- **Execution Time**: <5 minutes for complete pipeline (excluding manual steps)
- **Data Consistency**: 100% transactional integrity via pre-execution archiving
- **Change Detection Accuracy**: 100% identification of new upstream data
- **User Intervention**: Required only for manual downloads and mutation reviews
- **Archive Completeness**: 100% of outputs preserved with compression

## Functional Requirements

### Input Requirements

#### Dependency Graph Definition
```
Nodes and Edges:
- Amazon Order History Request → Amazon Order History Unzip
- Amazon Order History Unzip → Amazon Matching
- Apple Receipt Extraction → Apple Receipt Data Cleaning and Parsing
- Apple Receipt Data Cleaning and Parsing → Apple Matching
- YNAB Sync → Amazon Matching
- YNAB Sync → Apple Matching
- YNAB Sync → Cash Flow Analysis
- Amazon Matching → Split Generation
- Apple Matching → Split Generation
- Split Generation → YNAB Apply
- Retirement Account Updates → YNAB Account Updates
```

#### Change Detection Sources
- **YNAB API**: Check `server_knowledge` field for updates
- **Amazon Data**: Scan `data/amazon/raw/` for new directories
- **Apple Emails**: Query IMAP for emails since last fetch timestamp
- **Retirement Accounts**: Compare last update date against configured threshold

#### User Configuration
- **Date Filters**: Optional `--start` and `--end` parameters (default: no filtering)
- **Confidence Threshold**: `--confidence-threshold` for auto-approval (default: 1.0)
- **Performance Metrics**: `--perf` flag for detailed timing and statistics
- **Interactive Mode**: Default behavior with prompts for manual steps
- **Non-Interactive Mode**: `--non-interactive` flag for automated/scheduled runs

### Processing Requirements

#### Dependency Resolution
- **Graph Traversal**: Breadth-first approach to minimize redundant executions
- **Change Propagation**: Mark all downstream nodes as requiring execution when upstream changes
  detected
- **Idempotency**: Nodes only execute if they have changes or upstream dependencies changed
- **Synchronous Execution**: Execute nodes synchronously, without concurrency.
  Breadth-first traversal of the graph.

#### Archive Management
- **Transactional Archiving**: Archive all current outputs before any processing begins
- **Archive Structure**: `data/{domain}/archive/YYYY-MM-DD-NNN.tar.gz` with zero-padded sequence numbers
- **Compression**: All archives compressed as `.tar.gz` files
- **Retention Policy**: Keep all archives indefinitely
- **Archive Manifest**: Include metadata about what triggered the archive

#### Command Standardization
- **Unified Parameters**: Harmonized option names across all commands
  - Date ranges: `--start`, `--end`
  - Thresholds: `--confidence-threshold`
  - Output control: `--verbose`, `--quiet`
  - Execution mode: `--dry-run`, `--force`
- **Result Structure**: Standardized Python return objects from each command
- **Error Handling**: Consistent exception types and error codes

#### Node Implementations

##### YNAB Sync Node
- **Command**: `finances ynab sync-cache`
- **Change Detection**: Compare cached `server_knowledge` with API response
- **Outputs**: `data/ynab/cache/{accounts,categories,transactions}.json`
- **Dependencies**: None (root node)

##### Amazon Order History Request Node
- **Command**: Interactive prompt for manual download
- **User Actions**:
  1. Option to skip
  2. Prompt for downloaded directory path
  3. Validate directory structure
- **Dependencies**: None (root node)

##### Amazon Order History Unzip Node
- **Command**: `finances amazon unzip`
- **Change Detection**: New `.zip` files in download directory
- **Outputs**: Extracted order data in `data/amazon/raw/`
- **Dependencies**: Amazon Order History Request

##### Amazon Matching Node
- **Command**: `finances amazon match`
- **Change Detection**: New data in `data/amazon/raw/` or YNAB cache update
- **Outputs**: `data/amazon/transaction_matches/YYYY-MM-DDTHH-MM-SS_results.json`
- **Dependencies**: YNAB Sync, Amazon Order History Unzip

##### Apple Receipt Extraction Node
- **Command**: `finances apple fetch-emails`
- **Change Detection**: IMAP query for new emails
- **Outputs**: `data/apple/emails/YYYY-MM-DD_HH-MM-SS_apple_emails/`
- **Dependencies**: None (root node)

##### Apple Receipt Parsing Node
- **Command**: `finances apple parse-receipts`
- **Change Detection**: New email directories
- **Outputs**: `data/apple/exports/YYYY-MM-DD_HH-MM-SS_apple_receipts_export/`
- **Dependencies**: Apple Receipt Extraction

##### Apple Matching Node
- **Command**: `finances apple match`
- **Change Detection**: New parsed receipts or YNAB cache update
- **Outputs**: `data/apple/transaction_matches/YYYY-MM-DD_HH-MM-SS_results.json`
- **Dependencies**: YNAB Sync, Apple Receipt Parsing

##### Split Generation Node
- **Command**: `finances ynab generate-splits`
- **Change Detection**: New match results from Amazon or Apple
- **Outputs**: `data/ynab/mutations/YYYY-MM-DD_HH-MM-SS_{source}_mutations.yaml`
- **Dependencies**: YNAB Sync, Amazon Matching, Apple Matching
- **Special Behavior**: Aggregate results from all upstream matchers

##### YNAB Apply Node
- **Command**: `finances ynab apply-mutations`
- **Interactive Features**:
  - Display summary of proposed changes
  - Show confidence scores and auto-approval counts
  - Prompt for confirmation before applying
  - Option to abort flow execution
- **Dependencies**: Split Generation

##### Retirement Account Updates Node
- **Command**: `finances retirement update`
- **Interactive Flow**:
  1. List tracked retirement accounts
  2. For each account:
     - Show last update date and balance
     - Prompt for new balance (or skip)
     - Optional: prompt for as-of date (default: today)
  3. Create adjustment transactions in YNAB
- **Outputs**: `data/retirement/balance_history.yaml`
- **Dependencies**: None (root node)

##### Cash Flow Analysis Node
- **Command**: `finances cashflow analyze`
- **Change Detection**: YNAB cache updates
- **Outputs**: `data/cash_flow/charts/YYYY-MM-DD_HH-MM-SS_dashboard.png`
- **Dependencies**: YNAB Sync

### Output Requirements

#### JSON Artifacts
- **Formatting**: Pretty printed and line wrapped at 100 characters,
    for readability and greppability.

#### Progress Reporting
- **Stage Indicators**: Display "[X/Y] Executing: {node_name}" for each stage
- **Change Detection Results**: Report what changes triggered each node execution
- **Command Output**: Pass through individual command output to terminal
- **Summary Statistics**: Final report of nodes executed, skipped, and failed

#### Performance Metrics (with --perf flag)
- **Per-Node Metrics**:
  - Wall clock time
  - Number of items processed
  - API calls made (where applicable)
  - Memory usage
- **Aggregate Metrics**:
  - Total execution time
  - Total YNAB mutations generated
  - New transactions discovered
  - Archive size created

#### Review Artifacts
- **Mutation Files**: YAML format with clear next steps documentation
- **Non-Interactive Summary**: Generated when `--non-interactive` flag used
  - Location of all generated artifacts
  - Commands to manually review mutations
  - Instructions for applying approved changes

#### Error Reporting
- **Immediate Stop**: Halt execution on any error
- **Error Context**: Display which node failed and why
- **Recovery Instructions**: Provide steps to resolve and retry
- **Archive State**: Confirm that pre-execution archives are available

## Technical Architecture

### Dependency Declaration System

#### Decorator-Based Approach
```python
@flow_node(
    name="amazon_matching",
    depends_on=["ynab_sync", "amazon_unzip"]
)
def amazon_match_command(ctx, **kwargs):
    # Command implementation
    return FlowResult(
        success=True,
        items_processed=150,
        outputs=["data/amazon/transaction_matches/..."]
    )
```

#### Class-Based Alternative
```python
class AmazonMatchCommand(FlowNode):
    name = "amazon_matching"

    def get_dependencies(self):
        return ["ynab_sync", "amazon_unzip"]

    def check_changes(self):
        # Return True if execution needed
        pass

    def execute(self, ctx, **kwargs):
        # Command implementation
        return FlowResult(...)
```

### Execution Engine

#### Graph Construction
- **Dynamic Discovery**: Scan all registered commands for dependency declarations
- **Validation**: Ensure graph is acyclic and all dependencies exist

#### Change Detection Pipeline
1. **Root Nodes**: Check all nodes without dependencies for changes
2. **Propagation**: Mark downstream nodes of any changed root nodes
3. **Breadth-First Execution**: Process nodes level by level
4. **Result Aggregation**: Collect results from all executed nodes

#### Archive Transaction
```python
def begin_flow_transaction():
    archive_timestamp = datetime.now()
    archive_manifest = {}

    for domain in ["amazon", "apple", "ynab", "cash_flow"]:
        current_files = list_current_outputs(domain)
        if current_files:
            archive_path = create_archive(domain, archive_timestamp, current_files)
            archive_manifest[domain] = archive_path

    return archive_manifest
```

### Integration Points

#### Command Return Structure
```python
@dataclass
class FlowResult:
    success: bool
    items_processed: int
    new_items: int
    updated_items: int
    outputs: List[Path]
    requires_review: bool
    review_instructions: Optional[str]
```

#### Flow Context
```python
@dataclass
class FlowContext:
    start_time: datetime
    interactive: bool
    performance_tracking: bool
    confidence_threshold: int
    date_range: Optional[Tuple[date, date]]
    archive_manifest: Dict[str, Path]
    execution_history: List[NodeExecution]
```

Note: `confidence_threshold` avoids the use of `float` to avoid floating point math inaccuracies.
We prefer decimal or fixed-point for all math.

## Quality Assurance

### Data Validation
- **Archive Integrity**: Verify all archives compress successfully
- **Node Output Validation**: Each node validates its outputs before returning
- **Dependency Satisfaction**: Confirm all required inputs exist before node execution
- **Result Consistency**: Validate that node results match expected schemas

### Edge Case Handling
- **Empty Results**: Gracefully handle nodes that find no new data to process
- **Partial Data**: Continue processing available accounts if some are missing
- **Network Failures**: Retry transient failures with exponential backoff
- **Manual Step Skips**: Allow flow continuation when manual steps are skipped

### Error Recovery
- **Archive Rollback**: Document how to restore from transaction archives
- **Partial Execution**: Clear reporting of what succeeded before failure
- **Retry Capability**: Individual node re-execution without full flow restart
- **Debug Mode**: Verbose logging for troubleshooting failures

## Future Enhancements

### Near-Term Improvements
- **Scheduled Execution**: Cron-compatible non-interactive mode
- **Notification System**: Email/Slack alerts for flow completion
- **Incremental Processing**: Process only changed items within large datasets
- **Parallel Execution**: Run independent nodes concurrently

### Advanced Features
- **Web Dashboard**: Visual flow execution monitoring
- **Historical Analytics**: Trends in processing times and data volumes
- **Smart Scheduling**: Predict optimal execution times based on data patterns
- **Differential Archives**: Store only changes between archive generations

## Implementation Verification

### Success Validation
- **Flow Execution Test**: Complete flow runs without errors
- **Archive Creation**: Verify archives created before processing
- **Change Detection**: Confirm only changed nodes execute
- **Error Handling**: Validate immediate stop on failures

### Performance Metrics
- **Execution Time**: <5 minutes for typical flow
- **Archive Size**: <100MB compressed for typical dataset
- **Memory Usage**: <500MB peak during execution
- **API Efficiency**: <100 YNAB API calls per flow

---

## Document History

- **2025-09-24**: Initial specification created
- **Version**: 1.0
- **Status**: Complete System Specification
- **Owner**: Karl Davis

---
