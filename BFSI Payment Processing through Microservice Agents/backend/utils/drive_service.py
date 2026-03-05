import os
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import zipfile
import tempfile

try:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.errors import HttpError
    import io
except ImportError:
    logging.warning("Google API client libraries not installed. Drive service will be limited.")
    build = None

logger = logging.getLogger(__name__)

class GoogleDriveService:
    def __init__(self):
        """Initialize Google Drive Service"""
        self.credentials = None
        self.service = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Scopes required for the application
        self.SCOPES = ['https://www.googleapis.com/auth/drive.file']
        
        # Folder IDs for organization
        self.folder_ids = {
            'logs': None,
            'code': None,
            'backups': None
        }
        
        # Initialize service
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Drive service with authentication"""
        try:
            if not build:
                logger.warning("Google API client not available. Drive features disabled.")
                return
            
            credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS')
            token_path = os.getenv('GOOGLE_DRIVE_TOKEN', 'data/drive_token.json')
            
            if not credentials_path or not os.path.exists(credentials_path):
                logger.warning("Google Drive credentials not found. Drive service disabled.")
                return
            
            # Load existing credentials
            if os.path.exists(token_path):
                try:
                    self.credentials = Credentials.from_authorized_user_file(token_path, self.SCOPES)
                except Exception as e:
                    logger.error(f"Error loading Drive credentials: {str(e)}")
            
            # If credentials are not valid, refresh or re-authenticate
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    try:
                        self.credentials.refresh(Request())
                    except Exception as e:
                        logger.error(f"Error refreshing Drive credentials: {str(e)}")
                        self.credentials = None
                
                if not self.credentials:
                    try:
                        flow = InstalledAppFlow.from_client_secrets_file(credentials_path, self.SCOPES)
                        self.credentials = flow.run_local_server(port=0)
                    except Exception as e:
                        logger.error(f"Error authenticating with Google Drive: {str(e)}")
                        return
                
                # Save credentials for future use
                try:
                    with open(token_path, 'w') as token:
                        token.write(self.credentials.to_json())
                except Exception as e:
                    logger.error(f"Error saving Drive credentials: {str(e)}")
            
            # Build the service
            self.service = build('drive', 'v3', credentials=self.credentials)
            
            # Create necessary folders
            self._setup_folders()
            
            logger.info("Google Drive service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Drive service: {str(e)}")
            self.service = None
    
    def _setup_folders(self):
        """Create necessary folders in Google Drive"""
        if not self.service:
            return
        
        try:
            folder_names = {
                'AI Payment System Logs': 'logs',
                'AI Payment System Code': 'code',
                'AI Payment System Backups': 'backups'
            }
            
            # Check if folders already exist
            results = self.service.files().list(
                q="mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()
            
            existing_folders = {file['name']: file['id'] for file in results.get('files', [])}
            
            # Create missing folders
            for folder_name, folder_key in folder_names.items():
                if folder_name in existing_folders:
                    self.folder_ids[folder_key] = existing_folders[folder_name]
                else:
                    folder_metadata = {
                        'name': folder_name,
                        'mimeType': 'application/vnd.google-apps.folder'
                    }
                    
                    folder = self.service.files().create(
                        body=folder_metadata,
                        fields='id'
                    ).execute()
                    
                    self.folder_ids[folder_key] = folder.get('id')
                    logger.info(f"Created Drive folder: {folder_name}")
            
        except Exception as e:
            logger.error(f"Error setting up Drive folders: {str(e)}")
    
    def _upload_file_sync(self, file_path: str, drive_filename: str, folder_type: str = 'logs') -> Optional[str]:
        """Upload file to Google Drive synchronously"""
        if not self.service:
            logger.warning("Google Drive service not available")
            return None
        
        try:
            folder_id = self.folder_ids.get(folder_type)
            
            # File metadata
            file_metadata = {
                'name': drive_filename,
                'parents': [folder_id] if folder_id else []
            }
            
            # Upload file
            media = MediaFileUpload(file_path, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,createdTime'
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"File uploaded to Drive: {drive_filename} (ID: {file_id})")
            
            return file_id
            
        except Exception as e:
            logger.error(f"Error uploading file to Drive: {str(e)}")
            return None
    
    async def upload_file(self, file_path: str, drive_filename: str, folder_type: str = 'logs') -> Optional[str]:
        """Upload file to Google Drive asynchronously"""
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return None
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._upload_file_sync,
            file_path,
            drive_filename,
            folder_type
        )
    
    def _upload_content_sync(self, content: str, drive_filename: str, folder_type: str = 'logs') -> Optional[str]:
        """Upload content as file to Google Drive synchronously"""
        if not self.service:
            return None
        
        try:
            folder_id = self.folder_ids.get(folder_type)
            
            # File metadata
            file_metadata = {
                'name': drive_filename,
                'parents': [folder_id] if folder_id else []
            }
            
            # Upload content
            media = MediaIoBaseUpload(
                io.BytesIO(content.encode('utf-8')),
                mimetype='text/plain',
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,createdTime'
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"Content uploaded to Drive: {drive_filename}")
            
            return file_id
            
        except Exception as e:
            logger.error(f"Error uploading content to Drive: {str(e)}")
            return None
    
    async def upload_content(self, content: str, drive_filename: str, folder_type: str = 'logs') -> Optional[str]:
        """Upload content as file to Google Drive asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._upload_content_sync,
            content,
            drive_filename,
            folder_type
        )
    
    async def upload_logs(self, log_dir: str = 'logs') -> Dict[str, Any]:
        """Upload all log files to Google Drive"""
        if not self.service:
            return {"error": "Google Drive service not available"}
        
        try:
            log_path = Path(log_dir)
            if not log_path.exists():
                return {"error": f"Log directory not found: {log_dir}"}
            
            uploaded_files = []
            errors = []
            
            for log_file in log_path.glob('*.log'):
                try:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    drive_filename = f"{timestamp}_{log_file.name}"
                    
                    file_id = await self.upload_file(
                        str(log_file),
                        drive_filename,
                        'logs'
                    )
                    
                    if file_id:
                        uploaded_files.append({
                            'local_file': str(log_file),
                            'drive_filename': drive_filename,
                            'file_id': file_id
                        })
                    else:
                        errors.append(f"Failed to upload {log_file.name}")
                        
                except Exception as e:
                    errors.append(f"Error uploading {log_file.name}: {str(e)}")
            
            return {
                "success": True,
                "uploaded_files": uploaded_files,
                "errors": errors,
                "total_uploaded": len(uploaded_files)
            }
            
        except Exception as e:
            logger.error(f"Error uploading logs: {str(e)}")
            return {"error": str(e)}
    
    async def backup_source_code(self, source_dir: str = '.') -> Dict[str, Any]:
        """Create and upload source code backup"""
        if not self.service:
            return {"error": "Google Drive service not available"}
        
        try:
            # Create temporary zip file
            with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Create zip archive
            with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                source_path = Path(source_dir)
                
                # Include important directories and files
                include_patterns = [
                    'backend/**/*.py',
                    'frontend/**/*.py',
                    'config/**/*',
                    'requirements.txt',
                    'README.md',
                    '.env.example'
                ]
                
                exclude_patterns = [
                    '__pycache__',
                    '*.pyc',
                    '.git',
                    'logs',
                    'data/payment_system.db',
                    'venv',
                    'node_modules'
                ]
                
                for pattern in include_patterns:
                    for file_path in source_path.glob(pattern):
                        if file_path.is_file() and not any(excl in str(file_path) for excl in exclude_patterns):
                            # Calculate relative path
                            relative_path = file_path.relative_to(source_path)
                            zipf.write(file_path, relative_path)
            
            # Upload zip file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"payment_system_backup_{timestamp}.zip"
            
            file_id = await self.upload_file(temp_path, backup_filename, 'backups')
            
            # Clean up temporary file
            os.unlink(temp_path)
            
            if file_id:
                return {
                    "success": True,
                    "backup_filename": backup_filename,
                    "file_id": file_id,
                    "timestamp": timestamp
                }
            else:
                return {"error": "Failed to upload backup"}
            
        except Exception as e:
            logger.error(f"Error creating source code backup: {str(e)}")
            return {"error": str(e)}
    
    async def upload_ai_generated_code(self, code_content: str, filename: str, description: str = "") -> Optional[str]:
        """Upload AI-generated code to Google Drive"""
        try:
            # Add metadata as comments
            timestamp = datetime.now().isoformat()
            header = f"""
# AI-Generated Code
# Generated: {timestamp}
# Description: {description}
# 
# This code was generated by the AI Payment System
# 

"""
            full_content = header + code_content
            
            # Upload to code folder
            file_id = await self.upload_content(
                full_content,
                filename,
                'code'
            )
            
            return file_id
            
        except Exception as e:
            logger.error(f"Error uploading AI-generated code: {str(e)}")
            return None
    
    def _list_files_sync(self, folder_type: str = 'logs', limit: int = 50) -> List[Dict[str, Any]]:
        """List files in Google Drive folder synchronously"""
        if not self.service:
            return []
        
        try:
            folder_id = self.folder_ids.get(folder_type)
            
            query = f"'{folder_id}' in parents and trashed=false" if folder_id else "trashed=false"
            
            results = self.service.files().list(
                q=query,
                pageSize=limit,
                fields="files(id,name,size,createdTime,modifiedTime)",
                orderBy="createdTime desc"
            ).execute()
            
            files = results.get('files', [])
            
            return [
                {
                    'id': file['id'],
                    'name': file['name'],
                    'size': int(file.get('size', 0)),
                    'created_time': file['createdTime'],
                    'modified_time': file['modifiedTime']
                }
                for file in files
            ]
            
        except Exception as e:
            logger.error(f"Error listing Drive files: {str(e)}")
            return []
    
    async def list_files(self, folder_type: str = 'logs', limit: int = 50) -> List[Dict[str, Any]]:
        """List files in Google Drive folder asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self._list_files_sync,
            folder_type,
            limit
        )
    
    async def get_storage_info(self) -> Dict[str, Any]:
        """Get Google Drive storage information"""
        if not self.service:
            return {"error": "Google Drive service not available"}
        
        try:
            loop = asyncio.get_event_loop()
            
            def get_info():
                about = self.service.about().get(fields="storageQuota,user").execute()
                return about
            
            info = await loop.run_in_executor(self.executor, get_info)
            
            storage_quota = info.get('storageQuota', {})
            user = info.get('user', {})
            
            # Get folder sizes
            folder_info = {}
            for folder_name, folder_id in self.folder_ids.items():
                if folder_id:
                    files = await self.list_files(folder_name, limit=1000)
                    total_size = sum(file.get('size', 0) for file in files)
                    folder_info[folder_name] = {
                        'file_count': len(files),
                        'total_size': total_size
                    }
            
            return {
                "user_email": user.get('emailAddress'),
                "total_storage": int(storage_quota.get('limit', 0)),
                "used_storage": int(storage_quota.get('usage', 0)),
                "available_storage": int(storage_quota.get('limit', 0)) - int(storage_quota.get('usage', 0)),
                "folder_info": folder_info
            }
            
        except Exception as e:
            logger.error(f"Error getting Drive storage info: {str(e)}")
            return {"error": str(e)}
    
    def is_available(self) -> bool:
        """Check if Google Drive service is available"""
        return self.service is not None

# Initialize global Drive service
drive_service = GoogleDriveService()

# Convenience functions
async def upload_log_file(log_path: str, custom_name: Optional[str] = None) -> Optional[str]:
    """Upload a log file to Google Drive"""
    if not os.path.exists(log_path):
        logger.error(f"Log file not found: {log_path}")
        return None
    
    filename = custom_name or f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(log_path).name}"
    return await drive_service.upload_file(log_path, filename, 'logs')

async def upload_generated_code(code: str, filename: str, description: str = "") -> Optional[str]:
    """Upload AI-generated code to Google Drive"""
    return await drive_service.upload_ai_generated_code(code, filename, description)

async def backup_system() -> Dict[str, Any]:
    """Create system backup including logs and source code"""
    results = {
        "logs": await drive_service.upload_logs(),
        "source_code": await drive_service.backup_source_code(),
        "timestamp": datetime.now().isoformat()
    }
    
    return results