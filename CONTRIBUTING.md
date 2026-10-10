# Contributing to CivicTrace

Thank you for your interest in contributing to CivicTrace.

## Code of Conduct & Civic Mission
CivicTrace is built to preserve civic transparency, citizen rights, and infrastructure accountability. Contributions should maintain high standards of privacy, deterministic explainability, and accessible design.

## Development Setup
1. Clone the repository and configure `.env` based on `.env.example`.
2. Python virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r services/api/requirements.txt
   ```
3. Frontend setup:
   ```bash
   cd apps/web
   npm install
   npm run dev
   ```
4. Run tests before submitting a Pull Request:
   ```bash
   cd services/api
   python -m pytest app/tests/
   cd ../../apps/web
   npm run build
   ```
