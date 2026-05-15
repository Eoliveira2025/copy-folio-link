
import os
import shutil
import zipfile

def create_deploy_zip():
    zip_name = "copytrade-v3-metaapi-final-deploy.zip"
    
    # Files to include
    files_to_include = [
        "requirements.v3.txt",
        "backend/app/models/metaapi.py",
        "backend/app/schemas/metaapi.py",
        "backend/app/services/metaapi/service.py",
        "backend/app/services/metaapi/client.py",
        "backend/app/services/metaapi/copyfactory.py",
        "backend/app/api/routes/metaapi_admin.py",
        "backend/app/main.py",
        ".env.v3.example",
    ]
    
    # Directories to include
    dirs_to_include = [
        "backend/app/services/metaapi",
        "scripts",
    ]

    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add individual files
        for file_path in files_to_include:
            if os.path.exists(file_path):
                zipf.write(file_path)
            else:
                print(f"Warning: {file_path} not found")

        # Add directories
        for dir_path in dirs_to_include:
            if os.path.exists(dir_path):
                for root, dirs, files in os.walk(dir_path):
                    for file in files:
                        if "__pycache__" not in root:
                            file_full_path = os.path.join(root, file)
                            zipf.write(file_full_path)
            else:
                print(f"Warning: directory {dir_path} not found")

    print(f"Created {zip_name}")

if __name__ == "__main__":
    create_deploy_zip()
