#!/usr/bin/env python3
"""Simple FHIR MCP Server - Provides tools to list and apply PlanDefinitions from a FHIR R4 server."""
import os
import sys
import logging
import json
import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("fhir-server")

# Initialize MCP server
mcp = FastMCP("fhir")

# Configuration
FHIR_BASE_URL = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir")


def format_plan_definition(plan_def: dict) -> str:
    """Format a single PlanDefinition for display."""
    pd_id = plan_def.get("id", "Unknown")
    title = plan_def.get("title", plan_def.get("name", "Untitled"))
    status = plan_def.get("status", "unknown")
    description = plan_def.get("description", "No description available")
    version = plan_def.get("version", "N/A")
    url = plan_def.get("url", "N/A")
    
    # Get action count if available
    actions = plan_def.get("action", [])
    action_count = len(actions) if actions else 0
    
    return f"""📋 **{title}**
   ID: {pd_id}
   Status: {status}
   Version: {version}
   URL: {url}
   Actions: {action_count}
   Description: {description[:200]}{"..." if len(description) > 200 else ""}"""


@mcp.tool()
async def list_plan_definitions(status: str = "", name: str = "", count: str = "20") -> str:
    """List available PlanDefinition resources from the FHIR server with optional filters for status and name."""
    logger.info(f"Listing PlanDefinitions with status={status}, name={name}, count={count}")
    
    try:
        # Build search parameters
        params = {"_count": count.strip() if count.strip() else "20"}
        
        if status.strip():
            params["status"] = status.strip()
        
        if name.strip():
            params["name:contains"] = name.strip()
        
        # Make request to FHIR server
        async with httpx.AsyncClient() as client:
            url = f"{FHIR_BASE_URL}/PlanDefinition"
            logger.info(f"Requesting: {url} with params: {params}")
            
            response = await client.get(
                url,
                params=params,
                headers={"Accept": "application/fhir+json"},
                timeout=30.0
            )
            response.raise_for_status()
            bundle = response.json()
        
        # Process results
        entries = bundle.get("entry", [])
        total = bundle.get("total", len(entries))
        
        if not entries:
            return "📋 No PlanDefinitions found matching the criteria."
        
        # Format each PlanDefinition
        formatted_plans = []
        for entry in entries:
            resource = entry.get("resource", {})
            if resource.get("resourceType") == "PlanDefinition":
                formatted_plans.append(format_plan_definition(resource))
        
        header = f"📋 **Found {total} PlanDefinition(s)** (showing {len(formatted_plans)})\n"
        separator = "\n" + "─" * 50 + "\n"
        
        return header + separator.join(formatted_plans)
        
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: HTTP {e.response.status_code} - {e.response.text[:200]}"
    except httpx.ConnectError as e:
        logger.error(f"Connection error: {e}")
        return f"❌ Connection Error: Unable to connect to FHIR server at {FHIR_BASE_URL}. Is the server running?"
    except Exception as e:
        logger.error(f"Error listing PlanDefinitions: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def apply_plan_definition(plan_definition_id: str = "", subject: str = "") -> str:
    """Apply a PlanDefinition to a subject using the FHIR $apply operation, returning a CarePlan or Bundle."""
    logger.info(f"Applying PlanDefinition {plan_definition_id} to subject {subject}")
    
    # Validate required parameters
    if not plan_definition_id.strip():
        return "❌ Error: plan_definition_id is required. Provide the ID of the PlanDefinition to apply."
    
    if not subject.strip():
        return "❌ Error: subject is required. Provide a reference like 'Patient/123' or just '123' for a Patient."
    
    plan_definition_id = plan_definition_id.strip()
    subject = subject.strip()
    
    # Normalize subject reference - if no resource type prefix, assume Patient
    if "/" not in subject:
        subject = f"Patient/{subject}"
    
    try:
        async with httpx.AsyncClient() as client:
            # Build the $apply URL
            url = f"{FHIR_BASE_URL}/PlanDefinition/{plan_definition_id}/$apply"
            params = {"subject": subject}
            
            logger.info(f"Requesting: {url} with params: {params}")
            
            response = await client.get(
                url,
                params=params,
                headers={"Accept": "application/fhir+json"},
                timeout=60.0
            )
            response.raise_for_status()
            result = response.json()
        
        # Return the full FHIR JSON response
        return json.dumps(result, indent=2)
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        # Try to return the full error response as JSON
        try:
            error_json = json.loads(e.response.text)
            return json.dumps(error_json, indent=2)
        except json.JSONDecodeError:
            return f"❌ FHIR Server Error: HTTP {e.response.status_code}\n{e.response.text}"
    except httpx.ConnectError as e:
        logger.error(f"Connection error: {e}")
        return f"❌ Connection Error: Unable to connect to FHIR server at {FHIR_BASE_URL}. Is the server running?"
    except Exception as e:
        logger.error(f"Error applying PlanDefinition: {e}")
        return f"❌ Error: {str(e)}"


# === SERVER STARTUP ===
if __name__ == "__main__":
    logger.info("Starting FHIR MCP server...")
    logger.info(f"FHIR Base URL: {FHIR_BASE_URL}")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)