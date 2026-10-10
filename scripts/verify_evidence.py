#!/usr/bin/env python3
import sys
import argparse
from app.services.export_service import ExportService

def main():
    parser = argparse.ArgumentParser(
        description="CivicTrace Cryptographic Export Verification Tool. Validates artifact digests against canonical manifest."
    )
    parser.add_argument("package_path", help="Path to exported .zip case package")
    args = parser.parse_args()

    is_valid, logs = ExportService.verify_export_package(args.package_path)
    for log in logs:
        print(log)

    if not is_valid:
        sys.exit(1)
    else:
        print("\nIntegrity Verification Result: PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
