# FHIR PlanDefinition MCP Server

A Model Context Protocol (MCP) server that provides tools to interact with FHIR R4 PlanDefinition resources.

## Purpose

This MCP server enables AI assistants to:
- List available PlanDefinition resources from a FHIR server
- Apply PlanDefinitions to subjects using the FHIR $apply operation

## Features

### Current Implementation
- **`list_plan_definitions`** - Search and list PlanDefinition resources with optional filtering by status and name
- **`apply_plan_definition`** - Execute the $apply operation on a PlanDefinition for a given subject (Patient, Practitioner, etc.)

## Prerequisites

- Docker Desktop with MCP Toolkit enabled
- Docker MCP CLI plugin (`docker mcp` command)
- A running FHIR R4 server (default: http://localhost:8080/fhir)

## Configuration

The server uses the following environment variable:
- `FHIR_BASE_URL` - The base URL of your FHIR server (default: `http://localhost:8080/fhir`)

## Installation

See the step-by-step instructions in the INSTALLATION section below.

## Usage Examples

In Claude Desktop, you can ask:

**Listing PlanDefinitions:**
- "List all available plan definitions"
- "Show me active plan definitions"
- "Find plan definitions with 'diabetes' in the name"

**Applying PlanDefinitions:**
- "Apply plan definition 'example' to patient 123"
- "Execute the diabetes-management plan for Patient/456"

## Architecture

```
Claude Desktop → MCP Gateway → FHIR MCP Server → FHIR R4 Server
                                    ↓
                              HTTP requests to
                              /PlanDefinition
                              /PlanDefinition/{id}/$apply
```

## FHIR Operations

### List PlanDefinitions
Performs a FHIR search on the PlanDefinition resource:
```
GET [base]/PlanDefinition?_count=20&status=active&name:contains=example
```

### Apply PlanDefinition
Invokes the $apply operation:
```
GET [base]/PlanDefinition/{id}/$apply?subject=Patient/123
```

The $apply operation returns:
- **R4**: A CarePlan with activities and contained resources
- **Some implementations**: A Bundle or RequestGroup

## Development

### Local Testing

```bash
# Set environment variable for testing
export FHIR_BASE_URL="http://localhost:8080/fhir"

# Run directly
python fhir_server.py

# Test MCP protocol
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python fhir_server.py
```

### Adding New Tools

1. Add the function to `fhir_server.py`
2. Decorate with `@mcp.tool()`
3. Use single-line docstrings only
4. Update the catalog entry with the new tool name
5. Rebuild the Docker image

## Troubleshooting

### Tools Not Appearing
- Verify Docker image built successfully
- Check catalog and registry files
- Ensure Claude Desktop config includes custom catalog
- Restart Claude Desktop

### Connection Errors
- Verify FHIR server is running at the configured URL
- Check network connectivity (Docker may need host.docker.internal for localhost)
- Review server logs: `docker logs <container_name>`

### FHIR Errors
- Ensure PlanDefinition ID exists on the server
- Verify subject reference format (e.g., "Patient/123")
- Check FHIR server logs for detailed error messages

## Network Note for Docker

If your FHIR server runs on localhost, you may need to use `host.docker.internal` instead:
```
FHIR_BASE_URL=http://host.docker.internal:8080/fhir
```

## License

MIT License