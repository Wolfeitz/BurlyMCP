Burly MCP Documentation
=======================

Burly MCP is a secure Model Context Protocol (MCP) server implementation with comprehensive security features, audit logging, and policy enforcement.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   configuration
   security
   api/index
   contributing

Features
--------

* **Security-First Design**: Comprehensive path traversal protection, input validation, and security auditing
* **Policy Enforcement**: YAML-based policy configuration with tool whitelisting and argument validation
* **Audit Logging**: Structured JSON audit logs for all operations with security event tracking
* **Docker Integration**: Secure Docker operations with container management and monitoring
* **Notification System**: Pluggable notification framework supporting multiple providers
* **Resource Limits**: Configurable resource limits and timeout enforcement for tool execution

Quick Start
-----------

1. Install Burly MCP:

   .. code-block:: bash

      pip install burly-mingo-mcp

2. Create a configuration directory:

   .. code-block:: bash

      mkdir -p ~/.burly_mcp
      cp config/policy.yaml ~/.burly_mcp/

3. Run the server:

   .. code-block:: bash

      burly-mingo-mcp

Security
--------

Burly MCP implements multiple layers of security:

* **Path Validation**: All file operations are validated against configured root directories
* **Command Sanitization**: Shell commands are sanitized and validated before execution
* **Resource Limits**: Configurable limits on memory, CPU, and execution time
* **Audit Logging**: Comprehensive logging of all operations for security monitoring
* **Policy Enforcement**: YAML-based policies control which tools can be executed

See the :doc:`security` documentation for detailed information.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`