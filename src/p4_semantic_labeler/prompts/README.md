# Runtime prompts

Each operational instruction to a model is a separately versioned UTF-8 file in this package. The application loads these assets by their approved names and interpolates only the documented output constraints. Incoming names, documents, and source code remain untrusted reference data. Modify template files to change model wording; no operational instructions should be embedded in Python source.
