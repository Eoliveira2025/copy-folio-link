import zipfile
import os

files_to_zip = [
    'backend/app/services/metaapi/client.py',
    'backend/app/services/metaapi/service.py',
    'backend/app/schemas/metaapi.py',
    'backend/app/api/routes/metaapi_admin.py'
]

zip_name = 'public/copytrade-v3-metaapi-patch-v2.zip'

# Ensure public dir exists
if not os.path.exists('public'):
    os.makedirs('public')

with zipfile.ZipFile(zip_name, 'w') as zipf:
    for file in files_to_zip:
        if os.path.exists(file):
            zipf.write(file)
            print(f"Added {file}")
        else:
            print(f"Warning: {file} not found")

print(f"Zip created at {zip_name}")
