# api/services/
#
# Process-wide singletons and orchestration glue between the HTTP
# layer (routers/) and the existing backend modules. No business
# logic here — retrieval, generation, chunking, and storage all stay
# in the root modules exactly as they were.
