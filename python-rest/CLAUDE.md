# CLAUDE.md - Implementation Guide for FHIR Immunization MCP Server

## Overview

This MCP server provides FHIR R4 integration focused on immunization workflows, with specific support for the WHO SMART Immunizations Implementation Guide. The server enables AI assistants to interact with FHIR servers to manage vaccination protocols, patient records, and clinical decision support.

## Key FHIR Concepts

### PlanDefinition

A PlanDefinition represents a pre-defined group of actions (like a vaccination protocol). The WHO SMART Immunizations IG defines many PlanDefinitions for different vaccines and scenarios:

- **IMMZD2DT*** - Decision tables for determining vaccine eligibility
- **IMMZD5DT*** - Contraindication checking
- **IMMZD18S*** - Vaccination schedules

### $apply Operation

The `$apply` operation takes a PlanDefinition and applies it to a specific patient context, producing:
- A **CarePlan** (FHIR R4) with recommended activities
- Or a **Bundle** containing a RequestGroup and related resources (R5 style)

The operation evaluates CQL logic, checks conditions, and generates personalized recommendations.

### Key Resources

1. **Patient** - The subject of care
2. **Immunization** - Record of vaccine administration
3. **Observation** - Clinical findings (e.g., weight, allergies, screening results)
4. **CarePlan** - Generated plan with recommended activities
5. **ValueSet/CodeSystem** - Terminology resources

## Workflow Patterns

### Typical Immunization Workflow

1. **Find/Create Patient**
   ```
   search_patients(name="John Doe")
   # or
   create_patient(family_name="Doe", given_name="John", birth_date="2020-01-15")
   ```

2. **Check Immunization History**
   ```
   get_patient_immunizations(patient_id="123")
   ```

3. **List Available Protocols**
   ```
   list_plan_definitions(status="active")
   ```

4. **Get Protocol Details**
   ```
   get_plan_definition(plan_definition_id="IMMZD2DTMeaslesLowTransmission")
   ```

5. **Apply Protocol to Generate Recommendations**
   ```
   apply_plan_definition(
       plan_definition_id="IMMZD2DTMeaslesLowTransmission",
       subject="Patient/123"
   )
   ```

6. **Record Required Observations (if needed)**
   ```
   create_observation(
       patient_id="123",
       code="29463-7",
       code_system="http://loinc.org",
       code_display="Body Weight",
       value_quantity="8.5",
       value_unit="kg"
   )
   ```

7. **Record Immunization**
   ```
   create_immunization(
       patient_id="123",
       vaccine_code="05",
       vaccine_system="http://hl7.org/fhir/sid/cvx",
       vaccine_display="Measles",
       dose_number="1"
   )
   ```

### Terminology Lookup Pattern

```
# Find relevant ValueSet
search_valueset(name="measles")

# Get codes in ValueSet
expand_valueset(valueset_url="http://example.org/ValueSet/measles-vaccines")

# Look up specific code
lookup_code(system="http://hl7.org/fhir/sid/cvx", code="05")
```

## WHO SMART Immunizations IG

### Key URLs

- Implementation Guide: https://worldhealthorganization.github.io/smart-immunizations/
- Artifacts Index: https://worldhealthorganization.github.io/smart-immunizations/artifacts.html

### Common CodeSystems

- **CVX** (Vaccine codes): `http://hl7.org/fhir/sid/cvx`
- **SNOMED CT**: `http://snomed.info/sct`
- **LOINC** (Observations): `http://loinc.org`
- **ICD-11**: `http://id.who.int/icd/release/11/mms`

### Observation Codes for Immunizations

Common LOINC codes for pre-vaccination screening:

- `29463-7` - Body Weight
- `8302-2` - Body Height
- `30525-0` - Age
- `82810-3` - Pregnancy status
- `46240-8` - History of disease

### Common Vaccine Codes (CVX)

- `05` - Measles
- `03` - MMR
- `20` - DTaP
- `10` - IPV (Polio)
- `19` - BCG
- `08` - Hepatitis B
- `133` - Pneumococcal conjugate PCV13
- `116` - Rotavirus

## Error Handling

The server handles common FHIR errors:

- **404** - Resource not found
- **400** - Bad request (invalid parameters)
- **422** - Unprocessable entity (validation errors)

Error responses include details from the FHIR server when available.

## Environment Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| FHIR_BASE_URL | http://localhost:8080/fhir | Base URL of FHIR R4 server |

## Docker Networking

When running in Docker, use `host.docker.internal` to access services on the host:

```yaml
env:
  - name: FHIR_BASE_URL
    value: "http://host.docker.internal:8080/fhir"
```

## Tool Parameters

All tool parameters:
- Use empty string defaults (`""`) not `None`
- Should be checked with `.strip()` before use
- Are optional unless explicitly required by the function

## Response Formatting

Tools return formatted strings with:
- Emojis for visual clarity (📋 📄 💉 👤 etc.)
- Markdown formatting for structure
- JSON code blocks for raw data when needed

## Testing with HAPI FHIR

To run a local HAPI FHIR server with Clinical Reasoning support:

```bash
docker run -p 8080:8080 hapiproject/hapi:latest
```

For WHO SMART Immunizations, you'll need to load the IG resources:
1. Download the IG package from the IG publisher output
2. POST the resources to your FHIR server

## Limitations

1. **No Authentication** - Current implementation doesn't include SMART on FHIR auth
2. **No CQL Evaluation** - Relies on FHIR server for CQL evaluation in $apply
3. **R4 Focus** - Designed for FHIR R4, may need adjustments for R5

## Future Enhancements

- SMART on FHIR authentication support
- Batch operations for multiple patients
- ImmunizationRecommendation resource support
- AEFI (Adverse Event Following Immunization) reporting
- Integration with immunization registries