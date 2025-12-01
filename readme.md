# FHIR Immunization MCP Server

A Model Context Protocol (MCP) server for interacting with FHIR R4 servers to support immunization workflows, including WHO SMART Immunizations PlanDefinitions.

## Purpose

This MCP server provides a secure interface for AI assistants to:

- List and retrieve PlanDefinitions (vaccination protocols)
- Apply PlanDefinitions to patients using the `$apply` operation to generate CarePlans
- Query patient immunization history
- Create Immunization and Observation records
- Look up terminology (CodeSystems and ValueSets)
- Support WHO SMART Immunizations Implementation Guide workflows

## Features

### PlanDefinition Operations
- **`list_plan_definitions`** - List available PlanDefinitions with optional status/title filters
- **`get_plan_definition`** - Get detailed information about a specific PlanDefinition including actions, conditions, and data requirements
- **`apply_plan_definition`** - Apply a PlanDefinition to a patient using `$apply` operation, returning a CarePlan
- **`get_plan_definition_data_requirements`** - Get data requirements for a PlanDefinition

### Patient Operations
- **`search_patients`** - Search for patients by name, identifier, or birthdate
- **`get_patient`** - Get detailed patient information
- **`create_patient`** - Create a new Patient resource
- **`get_patient_immunizations`** - Get immunization history for a patient

### Immunization Operations
- **`create_immunization`** - Create a new Immunization record

### Observation Operations
- **`create_observation`** - Create an Observation record (e.g., for pre-vaccination screening)

### Terminology Operations
- **`search_valueset`** - Search for ValueSets
- **`expand_valueset`** - Expand a ValueSet to get its codes using `$expand`
- **`search_codesystem`** - Search for CodeSystems
- **`lookup_code`** - Look up code details using `$lookup`

### Generic FHIR Operations
- **`get_fhir_resource`** - Get any FHIR resource by type and ID
- **`search_fhir_resources`** - Search for FHIR resources with custom parameters
- **`get_server_capability`** - Get the server's capability statement

## Prerequisites

- Docker Desktop with MCP Toolkit enabled
- Docker MCP CLI plugin (`docker mcp` command)
- A FHIR R4 server (e.g., HAPI FHIR with Clinical Reasoning enabled)

## Configuration

The server uses the following environment variable:

- `FHIR_BASE_URL` - The base URL of your FHIR server (default: `http://localhost:8080/fhir`)

## Installation

### Step 1: Build Docker Image

```bash
cd fhir-immunization-mcp-server
docker build -t fhir-immunization-mcp-server .
```

### Step 2: Create Custom Catalog

Create or edit `~/.docker/mcp/catalogs/custom.yaml`:

```yaml
version: 2
name: custom
displayName: Custom MCP Servers
registry:
  fhir-immunization:
    description: "FHIR R4 server integration for immunization workflows with WHO SMART Guidelines support"
    title: "FHIR Immunization Server"
    type: server
    dateAdded: "2025-01-01T00:00:00Z"
    image: fhir-immunization-mcp-server:latest
    ref: ""
    readme: ""
    toolsUrl: ""
    source: ""
    upstream: ""
    icon: ""
    tools:
      - name: list_plan_definitions
      - name: get_plan_definition
      - name: apply_plan_definition
      - name: get_plan_definition_data_requirements
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
      - name: get_server_capability
    env:
      - name: FHIR_BASE_URL
        example: "http://host.docker.internal:8080/fhir"
        description: "FHIR server base URL"
    metadata:
      category: integration
      tags:
        - fhir
        - healthcare
        - immunization
        - who
        - smart-guidelines
      license: MIT
      owner: local
```

### Step 3: Update Registry

Edit `~/.docker/mcp/registry.yaml` and add under the `registry:` key:

```yaml
registry:
  # ... existing servers ...
  fhir-immunization:
    ref: ""
```

### Step 4: Configure Claude Desktop

Find your Claude Desktop config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Add your custom catalog to the args array:

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

1. Quit Claude Desktop completely
2. Start Claude Desktop again
3. Your new tools should appear!

## Usage Examples

In Claude Desktop, you can ask:

### List Available Immunization Protocols
- "List all the available immunization PlanDefinitions"
- "Show me the measles vaccination protocols"
- "What active PlanDefinitions are available?"

### Apply a Protocol to a Patient
- "Apply the measles vaccination protocol to patient 12345"
- "Generate a CarePlan for patient ABC using the BCG immunization protocol"
- "What immunizations does patient 123 need according to the WHO guidelines?"

### Manage Patient Records
- "Search for patients named John Smith"
- "Show me patient 12345's immunization history"
- "Create a new patient: Jane Doe, born 2020-03-15, female"

### Record Immunizations
- "Record a measles vaccination for patient 123"
- "Create an immunization record: MMR vaccine, patient 456, lot number ABC123"

### Terminology Lookups
- "Look up the code 21 in CVX vaccine codes"
- "Expand the measles vaccine ValueSet"
- "Search for immunization-related ValueSets"

## Architecture

```
Claude Desktop → MCP Gateway → FHIR Immunization MCP Server → FHIR R4 Server
                                        ↓
                                Environment Variables
                                (FHIR_BASE_URL)
```

## WHO SMART Immunizations Support

This server is designed to work with the WHO SMART Immunizations Implementation Guide, which provides:

- **PlanDefinitions** for various vaccination schedules (BCG, DTP, Measles, Polio, etc.)
- **ActivityDefinitions** for specific immunization activities
- **Decision support logic** using CQL (Clinical Quality Language)
- **ValueSets and CodeSystems** for immunization terminology

### Supported WHO SMART PlanDefinition Types

The server can work with PlanDefinitions following patterns like:
- `IMMZD2DT*` - Decision table PlanDefinitions for immunization eligibility
- `IMMZD5DT*` - Contraindication checking PlanDefinitions
- `IMMZD18S*` - Scheduling PlanDefinitions

## Development

### Local Testing

```bash
# Set environment variables
export FHIR_BASE_URL="http://localhost:8080/fhir"

# Run directly
python fhir_immunization_server.py

# Test MCP protocol
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python fhir_immunization_server.py
```

### Adding New Tools

1. Add the function to `fhir_immunization_server.py`
2. Decorate with `@mcp.tool()`
3. Use single-line docstrings
4. Default parameters to empty strings
5. Return formatted strings
6. Update the catalog entry with the new tool name
7. Rebuild the Docker image

## Troubleshooting

### Tools Not Appearing
- Verify Docker image built successfully
- Check catalog and registry files
- Ensure Claude Desktop config includes custom catalog
- Restart Claude Desktop

### Connection Errors
- Verify FHIR server is running and accessible
- Check FHIR_BASE_URL environment variable
- For local servers, use `host.docker.internal` instead of `localhost`

### $apply Operation Fails
- Ensure your FHIR server supports Clinical Reasoning operations
- Verify the PlanDefinition exists and is active
- Check that required patient data is available

## Security Considerations

- No authentication is currently implemented (suitable for development/testing)
- For production use, add OAuth2/SMART on FHIR authentication
- Running as non-root user in container
- Sensitive data logged only at debug level

## License

MIT License