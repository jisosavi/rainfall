"""Read-only data queries shared by the REST API (app.api) and the MCP server (app.mcp).

Routes and tools stay thin: they validate input, call these functions and shape the
response. Errors are raised as NotFoundError / InvalidRequestError; the REST API turns them
into 404 / 422, the MCP server into tool errors.
"""
