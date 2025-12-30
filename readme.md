# FHIR MCP Server

A Model Context Protocol (MCP) server for interacting with FHIR R4 servers. This server enables AI assistants to work with healthcare data, apply clinical protocols via PlanDefinitions, create and manage FHIR resources, and query medical terminology.

## Purpose

This MCP server provides a secure interface for AI assistants to:
- List and inspect PlanDefinitions (clinical protocols, order sets, decision support rules)
- Apply PlanDefinitions to generate CarePlans for patients
- Create, read, update, and delete any FHIR R4 resource using raw JSON
- Query CodeSystems and expand ValueSets for medical terminology lookup
- Work within ImplementationGuide contexts for specialized clinical workflows
- Support immunization workflows by recording Observations and related resources

## Features

### PlanDefinition Operations
- **`fhir_list_plan_definitions`** - List available PlanDefinitions with optional filters
- **`fhir_get_plan_definition`** - Get detailed view of a specific PlanDefinition including actions
- **`fhir_apply_plan_definition`** - Apply a PlanDefinition to generate a CarePlan for a subject

### Resource Management
- **`fhir_create_resource`** - Create any FHIR resource using raw JSON
- **`fhir_get_resource`** - Retrieve a resource by type and ID
- **`fhir_update_resource`** - Update an existing resource using raw JSON
- **`fhir_delete_resource`** - Delete a resource by type and ID
- **`fhir_search_resources`** - Search for resources with parameters

### Terminology Services
- **`fhir_lookup_code`** - Look up a code in a CodeSystem
- **`fhir_expand_valueset`** - Expand a ValueSet to get all codes
- **`fhir_list_codesystems`** - List available CodeSystems
- **`fhir_list_valuesets`** - List available ValueSets

### ImplementationGuide Context
- **`fhir_list_implementation_guides`** - List available ImplementationGuides
- **`fhir_get_implementation_guide`** - Get detailed ImplementationGuide information
- **`fhir_set_implementation_guide_context`** - Set the active ImplementationGuide context
- **`fhir_get_current_implementation_guide_context`** - View the current IG context

### Server Information
- **`fhir_get_server_capability`** - Get the server's CapabilityStatement

## Prerequisites

- Docker Desktop with MCP Toolkit enabled
- Docker MCP CLI plugin (`docker mcp` command)
- A running FHIR R4 server (default: http://localhost:8080/fhir)

## Installation

### Step 1: Save the Files

```bash
# Create project directory
mkdir fhir-mcp-server
cd fhir-mcp-server

# Save all files in this directory:
# - fhir_mcp_server.py
# - requirements.txt
# - Dockerfile
```

### Step 2: Build Docker Image

```bash
docker build -t fhir-mcp-server .
```

### Step 3: Create Custom Catalog

```bash
# Create catalogs directory if it doesn't exist
mkdir -p ~/.docker/mcp/catalogs

# Create or edit custom.yaml
nano ~/.docker/mcp/catalogs/custom.yaml
```

Add this entry to custom.yaml:

```yaml
version: 2
name: custom
displayName: Custom MCP Servers
registry:
  fhir:
    description: "FHIR R4 MCP Server for healthcare data and clinical protocols"
    title: "FHIR MCP Server"
    type: server
    dateAdded: "2025-01-01T00:00:00Z"
    image: fhir-mcp-server:latest
    ref: ""
    readme: ""
    toolsUrl: ""
    source: ""
    upstream: ""
    icon: ""
    tools:
      - name: fhir_list_plan_definitions
      - name: fhir_get_plan_definition
      - name: fhir_apply_plan_definition
      - name: fhir_create_resource
      - name: fhir_get_resource
      - name: fhir_update_resource
      - name: fhir_delete_resource
      - name: fhir_search_resources
      - name: fhir_lookup_code
      - name: fhir_expand_valueset
      - name: fhir_list_codesystems
      - name: fhir_list_valuesets
      - name: fhir_list_implementation_guides
      - name: fhir_get_implementation_guide
      - name: fhir_set_implementation_guide_context
      - name: fhir_get_current_implementation_guide_context
      - name: fhir_get_server_capability
    env:
      - name: FHIR_SERVER_URL
        value: "http://host.docker.internal:8080/fhir"
    metadata:
      category: integration
      tags:
        - healthcare
        - fhir
        - clinical
        - terminology
      license: MIT
      owner: local
```

### Step 4: Update Registry

```bash
# Edit registry file
nano ~/.docker/mcp/registry.yaml
```

Add this entry under the existing `registry:` key:

```yaml
registry:
  # ... existing servers ...
  fhir:
    ref: ""
```

### Step 5: Configure Claude Desktop

Find your Claude Desktop config file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

Edit the file and add your custom catalog to the args array:

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

Replace `YOUR_USERNAME` with your actual username.

### Step 6: Restart Claude Desktop

1. Quit Claude Desktop completely
2. Start Claude Desktop again
3. Your new FHIR tools should appear!

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FHIR_SERVER_URL` | `http://localhost:8080/fhir` | Base URL of the FHIR R4 server |

### Docker Network Access

If your FHIR server is running on the host machine, use `host.docker.internal` instead of `localhost`:

```yaml
env:
  - name: FHIR_SERVER_URL
    value: "http://host.docker.internal:8080/fhir"
```

## Usage Examples

In Claude Desktop, you can ask:

### PlanDefinitions
- "List all active PlanDefinitions on the FHIR server"
- "Show me the details of PlanDefinition/immunization-protocol"
- "Apply the immunization protocol to Patient/123"

### Resource Management
- "Create a new Patient resource with name John Doe, birthdate 1990-01-15"
- "Search for all Observations for Patient/123"
- "Get the full details of Observation/456"
- "Create an Observation to record the patient's vaccination"

### Terminology
- "What codes are available in the vaccine-administered ValueSet?"
- "Look up LOINC code 8302-2"
- "List all CodeSystems available on the server"

### ImplementationGuide
- "What ImplementationGuides are available?"
- "Set the immunization IG as the current context"
- "Show me the current ImplementationGuide context"

## Architecture

```
Claude Desktop → MCP Gateway → FHIR MCP Server → FHIR R4 Server
                                    ↓
                            HTTP/REST API
                            (application/fhir+json)
```

## Immunization Workflow Example

A typical immunization workflow might include:

1. **Set ImplementationGuide Context**:
   ```
   Set the immunization implementation guide as context
   ```

2. **Find the Protocol**:
   ```
   List PlanDefinitions related to immunization
   ```

3. **Apply the Protocol**:
   ```
   Apply PlanDefinition/immunization-schedule to Patient/john-doe
   ```

4. **Review the CarePlan**:
   The $apply operation returns a CarePlan with activities

5. **Create Required Resources**:
   ```
   Create an Immunization resource for the administered vaccine
   Create an Observation to record any adverse reactions
   ```

## Development

### Local Testing

```bash
# Set environment variables for testing
export FHIR_SERVER_URL="http://localhost:8080/fhir"

# Run directly
python fhir_mcp_server.py

# Test MCP protocol
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python fhir_mcp_server.py
```

### Adding New Tools

1. Add the function to `fhir_mcp_server.py`
2. Create a Pydantic input model
3. Decorate with `@mcp.tool()`
4. Update the catalog entry with the new tool name
5. Rebuild the Docker image

## Troubleshooting

### Tools Not Appearing
- Verify Docker image built successfully
- Check catalog and registry files for syntax errors
- Ensure Claude Desktop config includes custom catalog
- Restart Claude Desktop

### Connection Errors
- Verify FHIR server is running and accessible
- Check `FHIR_SERVER_URL` environment variable
- For host machine servers, use `host.docker.internal`

### FHIR Errors
- Check the OperationOutcome details in error messages
- Verify resource JSON is valid FHIR R4
- Ensure referenced resources exist

## Security Considerations

- Running as non-root user in container
- Sensitive data never logged
- No authentication credentials stored in code
- All communication with FHIR server is configurable

## License

MIT License

## References

- [FHIR R4 Specification](https://hl7.org/fhir/R4/)
- [PlanDefinition Resource](https://hl7.org/fhir/R4/plandefinition.html)
- [PlanDefinition $apply Operation](https://hl7.org/fhir/R4/plandefinition-operation-apply.html)
- [Model Context Protocol](https://modelcontextprotocol.io/)