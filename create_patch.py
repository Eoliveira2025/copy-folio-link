import zipfile
import os

files_to_patch = [
    'requirements.v3.txt',
    'backend/app/services/metaapi/copyfactory.py',
    'backend/app/services/metaapi/client.py',
    'backend/app/services/metaapi/service.py'
]

zip_name = 'copytrade-v3-metaapi-patch-copyfactory.zip'

with zipfile.ZipFile(zip_name, 'w') as zipf:
    for file in files_to_patch:
        if os.path.exists(file):
            zipf.write(file)
            print(f"Added {file}")
        else:
            print(f"Warning: {file} not found")

print(f"Patch ZIP created: {zip_name}")
