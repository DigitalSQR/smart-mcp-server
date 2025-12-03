# Multi-stage build for Kotlin FHIR Immunization MCP Server

# Stage 1: Build
FROM gradle:8.5-jdk17 AS builder

WORKDIR /app

# Copy Gradle files first for better caching
COPY build.gradle.kts settings.gradle.kts ./
COPY gradle.properties ./

# Download dependencies (cached layer)
RUN gradle dependencies --no-daemon || true

# Copy source code
COPY . ./src

# Build the shadow JAR
RUN gradle shadowJar --no-daemon

# Stage 2: Runtime
FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

# Create non-root user
RUN addgroup -g 1000 mcpuser && \
    adduser -u 1000 -G mcpuser -s /bin/sh -D mcpuser

# Copy the built JAR
COPY --from=builder /app/build/libs/fhir-immunization-mcp-server.jar ./server.jar

# Create data directory for FHIR resources
RUN mkdir -p /app/data && chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Set environment variables
ENV JAVA_OPTS="-Xmx512m -Xms256m"
ENV DATA_DIR="/app/data"

# Run the server
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar server.jar"]
