# CLAUDE.md - Implementation Guide for Kotlin FHIR Immunization MCP Server

## Overview

This is a Kotlin-based MCP server that provides local FHIR R4 resource management for immunization workflows. It uses the same HAPI FHIR libraries that power the Android FHIR SDK's FhirEngine.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client (Claude)                       │
└─────────────────────────┬───────────────────────────────────┘
                          │ JSON-RPC over stdio
┌─────────────────────────┴───────────────────────────────────┐
│                    MCP Kotlin SDK                            │
│  - Server class with tool registration                       │
│  - StdioServerTransport for communication                    │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────┐
│              FhirImmunizationServer.kt                       │
│  - Tool implementations                                      │
│  - FhirResourceStore (in-memory)                            │
│  - CarePlan generation                                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────────┐
│              HAPI FHIR Structures R4                         │
│  - Resource classes (Patient, Immunization, etc.)           │
│  - JSON parsing/serialization                                │
│  - Enumerations and data types                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### FhirResourceStore

An in-memory store simulating Android FHIR SDK's FhirEngine:

```kotlin
class FhirResourceStore {
    private val resources = mutableMapOf<String, MutableMap<String, Resource>>()
    
    fun <T : Resource> create(resource: T): String
    inline fun <reified T : Resource> get(id: String): T?
    inline fun <reified T : Resource> search(predicate: (T) -> Boolean): List<T>
    fun <T : Resource> update(resource: T): Boolean
    inline fun <reified T : Resource> delete(id: String): Boolean
}
```

### Tool Registration

Tools are registered using the MCP Kotlin SDK's DSL:

```kotlin
server.addTool(
    name = "tool_name",
    description = "Tool description"
) { request ->
    val args = request.arguments
    // Process arguments and return CallToolResult
    CallToolResult(content = listOf(TextContent("Result")))
}
```

### CarePlan Generation

Simplified $apply operation:

```kotlin
fun generateCarePlan(
    planDefinition: PlanDefinition, 
    patient: Patient, 
    encounterId: String?
): CarePlan {
    // Creates CarePlan from PlanDefinition actions
    // Sets subject, status, intent
    // Converts actions to activities
}
```

## HAPI FHIR Usage

### Creating Resources

```kotlin
val patient = Patient().apply {
    id = "123"
    addName(HumanName().apply {
        family = "Smith"
        addGiven("John")
    })
    gender = Enumerations.AdministrativeGender.MALE
    birthDateElement = DateType("2020-01-15")
}
```

### Parsing JSON

```kotlin
val fhirContext = FhirContext.forR4()
val jsonParser = fhirContext.newJsonParser()

// Parse
val resource = jsonParser.parseResource(jsonString) as Resource

// Serialize
val json = jsonParser.encodeResourceToString(resource)
```

### Searching Resources

```kotlin
val patients = resourceStore.search<Patient> { patient ->
    patient.nameFirstRep?.family?.contains("Smith") == true
}
```

## Android FHIR SDK Comparison

### FhirEngine API (Android)

```kotlin
// Android FHIR SDK
val fhirEngine = FhirEngineProvider.getInstance(context)

// Create
fhirEngine.create(patient)

// Read
val patient = fhirEngine.get<Patient>("123")

// Search
val results = fhirEngine.search<Patient> {
    filter(Patient.FAMILY, { value = "Smith" })
}
```

### This MCP Server

```kotlin
// This server
val resourceStore = FhirResourceStore()

// Create
resourceStore.create(patient)

// Read
val patient = resourceStore.get<Patient>("123")

// Search
val results = resourceStore.search<Patient> { 
    it.nameFirstRep?.family == "Smith" 
}
```

## WHO SMART Immunizations Support

### PlanDefinition Types

- `IMMZD2DT*` - Decision tables for immunization eligibility
- `IMMZD5DT*` - Contraindication checking
- `IMMZD18S*` - Vaccination schedules

### Loading WHO Resources

1. Download resources from the WHO SMART IG
2. Place JSON files in DATA_DIR
3. Server loads on startup

### Example PlanDefinition Structure

```json
{
  "resourceType": "PlanDefinition",
  "id": "IMMZD2DTMeaslesLowTransmission",
  "title": "Measles Low Transmission Protocol",
  "status": "active",
  "action": [
    {
      "title": "Administer MCV1",
      "condition": [
        {
          "kind": "applicability",
          "expression": {
            "language": "text/cql-identifier",
            "expression": "Due for MCV1"
          }
        }
      ],
      "definitionCanonical": "ActivityDefinition/MCV1"
    }
  ]
}
```

## Common Vaccine Codes (CVX)

| Code | Vaccine |
|------|---------|
| 03 | MMR |
| 05 | Measles |
| 08 | Hepatitis B |
| 10 | IPV (Polio) |
| 19 | BCG |
| 20 | DTaP |
| 116 | Rotavirus |
| 133 | PCV13 |

## Common LOINC Codes for Screening

| Code | Description |
|------|-------------|
| 29463-7 | Body Weight |
| 8302-2 | Body Height |
| 30525-0 | Age |
| 82810-3 | Pregnancy status |
| 46240-8 | History of disease |

## Error Handling

Tools return error messages in the result:

```kotlin
if (patientId.isNullOrBlank()) {
    return@addTool CallToolResult(
        content = listOf(TextContent("❌ Error: patient_id is required"))
    )
}
```

## Adding New Tools

1. Add tool registration in `registerTools()`:

```kotlin
server.addTool(
    name = "new_tool",
    description = "Description of new tool"
) { request ->
    // Implementation
    CallToolResult(content = listOf(TextContent("Result")))
}
```

2. Update the catalog with the new tool name

3. Rebuild the Docker image

## Testing

```kotlin
// Unit test example
@Test
fun `create patient stores resource`() {
    val store = FhirResourceStore()
    val patient = Patient().apply { 
        addName(HumanName().apply { family = "Test" })
    }
    
    val id = store.create(patient)
    val retrieved = store.get<Patient>(id)
    
    assertEquals("Test", retrieved?.nameFirstRep?.family)
}
```

## Performance Considerations

- In-memory storage is fast but limited by JVM heap
- For large datasets, consider persistent storage
- HAPI FHIR parsing has overhead for complex resources

## Security Notes

- No authentication implemented (add for production)
- In-memory data is not encrypted
- Container runs as non-root user
- No network access required (stdio transport)

## Debugging

Enable debug logging:

```kotlin
System.setProperty("org.slf4j.simpleLogger.defaultLogLevel", "debug")
```

View logs in stderr:

```bash
docker logs <container_id>
```