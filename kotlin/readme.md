# FHIR Immunization MCP Server (Kotlin)

**THIS IS NOT CURRENTLY WORKING AND IS A WORK IN PROGRESS**

A Model Context Protocol (MCP) server written in Kotlin for managing FHIR R4 resources with a focus on immunization workflows and WHO SMART Immunizations support.

## Overview

This MCP server uses the same HAPI FHIR libraries that power the [Android FHIR SDK](https://google.github.io/android-fhir/), providing a local FHIR resource store with CRUD operations and PlanDefinition processing. It's designed to work as a standalone MCP server that can be used with Claude Desktop or other MCP-compatible clients.

## Architecture

```
Claude Desktop → MCP Gateway → FHIR Immunization MCP Server (Kotlin)
                                         ↓
                              Local FHIR Resource Store
                              (HAPI FHIR Structures R4)
```

## Key Features

### Local FHIR Resource Storage
- In-memory FHIR resource store using HAPI FHIR Structures
- Same data model as Android FHIR SDK FhirEngine
- Support for all FHIR R4 resource types

### PlanDefinition Operations
- **`list_plan_definitions`** - List available vaccination protocols
- **`get_plan_definition`** - Get detailed protocol information
- **`apply_plan_definition`** - Generate CarePlan from PlanDefinition (simulates $apply)

### Patient Management
- **`search_patients`** - Search by name, identifier, birthdate
- **`get_patient`** - Get patient details
- **`create_patient`** - Create new patients

### Immunization Workflows
- **`get_patient_immunizations`** - Get vaccination history
- **`create_immunization`** - Record new immunizations
- **`create_observation`** - Record pre-vaccination screening observations

### Terminology Services
- **`search_valueset`** / **`expand_valueset`** - Work with ValueSets
- **`search_codesystem`** / **`lookup_code`** - Work with CodeSystems

### Generic FHIR Operations
- **`get_fhir_resource`** - Get any resource by type/ID
- **`search_fhir_resources`** - Search resources by type
- **`load_fhir_resource`** - Load resources from JSON
- **`get_store_summary`** - View store contents

## Prerequisites

- JDK 17 or higher
- Gradle 8.x (or use the wrapper)
- Docker (for containerized deployment)

## Building

### Local Build

```bash
# Clone the repository
cd fhir-immunization-mcp-server-kotlin

# Build the shadow JAR
./gradlew shadowJar

# The JAR will be at build/libs/fhir-immunization-mcp-server.jar
```

### Docker Build

```bash
docker build -t fhir-immunization-mcp-server .
```

## Running

### Direct Execution

```bash
# Run with stdio transport (for MCP)
java -jar build/libs/fhir-immunization-mcp-server.jar

# With custom data directory
DATA_DIR=/path/to/fhir/data java -jar build/libs/fhir-immunization-mcp-server.jar
```

### Docker Execution

```bash
# Run interactively
docker run -i --rm fhir-immunization-mcp-server

# With mounted data volume
docker run -i --rm -v /path/to/data:/app/data fhir-immunization-mcp-server
```

## Installation with Claude Desktop

### Step 1: Build the Docker Image

```bash
docker build -t fhir-immunization-mcp-server .
```

### Step 2: Create Custom Catalog

Create or edit `~/.docker/mcp/catalogs/custom.yaml`:

```yaml
version: 2
name: custom
displayName: Custom MCP Servers
registry:
  fhir-immunization-kotlin:
    description: "Kotlin FHIR R4 server with local storage for immunization workflows"
    title: "FHIR Immunization Server (Kotlin)"
    type: server
    dateAdded: "2025-01-01T00:00:00Z"
    image: fhir-immunization-mcp-server:latest
    ref: ""
    readme: ""
    tools:
      - name: list_plan_definitions
      - name: get_plan_definition
      - name: apply_plan_definition
      - name: search_patients
      - name: get_patient
      - name: create_patient
      - name: get_patient_immunizations
      - name: create_immunization
      - name: create_observation
      - name: search_valueset
      - name: expand_valueset
      - name: search_codesystem
      - name: lookup_code
      - name: get_fhir_resource
      - name: search_fhir_resources
      - name: load_fhir_resource
      - name: get_store_summary
    env:
      - name: DATA_DIR
        example: "/app/data"
        description: "Directory for loading FHIR resources on startup"
    metadata:
      category: integration
      tags:
        - fhir
        - healthcare
        - immunization
        - kotlin
        - who-smart
      license: MIT
      owner: local
```

### Step 3: Update Registry

Edit `~/.docker/mcp/registry.yaml`:

```yaml
registry:
  # ... existing servers ...
  fhir-immunization-kotlin:
    ref: ""
```

### Step 4: Configure Claude Desktop

Edit your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "mcp-toolkit-gateway": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", "/Users/YOUR_USERNAME/.docker/mcp:/mcp",
        "docker/mcp-gateway",
        "--catalog=/mcp/catalogs/docker-mcp.yaml",
        "--catalog=/mcp/catalogs/custom.yaml",
        "--config=/mcp/config.yaml",
        "--registry=/mcp/registry.yaml",
        "--tools-config=/mcp/tools.yaml",
        "--transport=stdio"
      ]
    }
  }
}
```

### Step 5: Restart Claude Desktop

## Loading FHIR Resources

### From Files

Place JSON files in the DATA_DIR directory. The server loads all `.json` files on startup:

```bash
# Example: load WHO SMART Immunization resources
cp PlanDefinition-IMMZD2DTMeasles.json /app/data/
cp Patient-example.json /app/data/
```

### At Runtime

Use the `load_fhir_resource` tool:

```
Load this FHIR resource: {"resourceType": "Patient", "name": [{"family": "Smith"}]}
```

## Usage Examples

### In Claude Desktop:

**List Vaccination Protocols:**
- "List all available PlanDefinitions"
- "Show me the measles vaccination protocols"

**Create and Manage Patients:**
- "Create a new patient: John Smith, born 2020-05-15, male"
- "Search for patients named Smith"

**Record Immunizations:**
- "Record a measles vaccination for patient 123"
- "What immunizations has patient ABC received?"

**Apply Protocols:**
- "Apply the measles PlanDefinition to patient 123"
- "Generate a CarePlan for patient ABC using BCG protocol"

**Terminology:**
- "Look up vaccine code 05 in the CVX system"
- "Expand the measles vaccine ValueSet"

## Comparison with Android FHIR SDK

| Feature | Android FHIR SDK | This MCP Server |
|---------|------------------|-----------------|
| Platform | Android | JVM (Docker/Server) |
| Storage | SQLite (encrypted) | In-memory |
| FHIR Library | HAPI FHIR Structures R4 | HAPI FHIR Structures R4 |
| Sync | Server sync support | Standalone |
| $apply | FhirOperator.generateCarePlan | Simplified CarePlan generation |
| CQL | Full CQL support | Not implemented |
| Use Case | Mobile apps | AI assistant integration |

## Technical Details

### Dependencies

- **MCP Kotlin SDK** (0.4.0) - Model Context Protocol implementation
- **HAPI FHIR** (6.10.5) - FHIR R4 resource handling
- **Ktor** - HTTP client for MCP transport
- **Kotlinx Coroutines** - Async operations
- **Kotlinx Serialization** - JSON handling

### Resource Storage

The `FhirResourceStore` class provides:
- `create(resource)` - Create/store a resource
- `get<T>(id)` - Get resource by type and ID
- `search<T>(predicate)` - Search with custom filter
- `update(resource)` - Update existing resource
- `delete<T>(id)` - Delete by type and ID

### CarePlan Generation

The `generateCarePlan()` function simulates the `$apply` operation:
1. Takes a PlanDefinition and Patient
2. Creates a CarePlan with DRAFT status
3. Converts PlanDefinition actions to CarePlan activities
4. Returns the generated CarePlan

For full CQL-based evaluation, consider using the Android FHIR SDK's Workflow Library.

## Limitations

1. **In-memory storage** - Data is not persisted across restarts
2. **No CQL evaluation** - Complex decision logic not supported
3. **Simplified $apply** - Basic CarePlan generation without condition evaluation
4. **No sync** - Standalone operation, no server synchronization

## Future Enhancements

- Persistent storage option (SQLite, PostgreSQL)
- CQL evaluation support
- SMART on FHIR authentication
- Full ActivityDefinition processing
- ImmunizationRecommendation generation

## License

MIT License
