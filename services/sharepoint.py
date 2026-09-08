import io
import os
import time
import requests
from typing import List, Optional, Dict, Any
from settings import settings
from services.excel_exporter import save_excel_to_disk

class SharePointService:
    """
    Servicio desacoplado para la interacción con Microsoft SharePoint
    mediante Microsoft Graph API utilizando Client Credentials (Azure AD).
    """

    def __init__(self):
        self.tenant_id = settings.AZURE_TENANT_ID
        self.client_id = settings.AZURE_CLIENT_ID
        self.client_secret = settings.AZURE_CLIENT_SECRET
        self.site_id = settings.SHAREPOINT_SITE_ID
        self.drive_id = settings.SHAREPOINT_DRIVE_ID
        self.folder_path = settings.SHAREPOINT_FOLDER_PATH.strip("/\\") if settings.SHAREPOINT_FOLDER_PATH else "Reportes"
        self.local_dir = settings.LOCAL_REPORTS_DIR or "generated_reports"
        
        # Cache de token de acceso
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        # Cache del site_id ya resuelto a ID compuesto (hostname,guid,guid)
        self._resolved_site_id: Optional[str] = None

    def is_configured(self) -> bool:
        """
        Verifica si las variables de entorno necesarias para conectar a SharePoint
        están presentes.
        """
        return bool(
            self.tenant_id
            and self.client_id
            and self.client_secret
            and self.site_id
        )

    def get_access_token(self) -> str:
        """
        Obtiene el token de acceso OAuth2 para Microsoft Graph.
        Utiliza cache en memoria mientras el token sea válido.
        """
        if not self.is_configured():
            raise ValueError(
                "Faltan credenciales de Azure AD / SharePoint en la configuración (.env)."
            )

        # Retornar token existente si aún no ha expirado (con margen de 60 segundos)
        if self._access_token and time.time() < (self._token_expires_at - 60):
            return self._access_token

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        
        response = requests.post(token_url, data=payload, timeout=20)
        if response.status_code != 200:
            raise RuntimeError(
                f"Error al autenticar con Azure AD ({response.status_code}): {response.text}"
            )

        data = response.json()
        self._access_token = data["access_token"]
        # expires_in suele ser 3599 segundos (1 hora)
        self._token_expires_at = time.time() + data.get("expires_in", 3600)
        return self._access_token

    def _resolve_site_id(self) -> str:
        """
        Resuelve self.site_id a un ID compuesto de Graph (hostname,site-guid,web-guid).

        Si SHAREPOINT_SITE_ID viene en formato de path (contiene ':', ej.
        'hostname:/sites/nombre:'), Graph no permite combinarlo con un segundo
        segmento ':...:' como 'root:/carpeta/archivo:' en la misma request. Por
        eso se resuelve una sola vez a su ID compuesto real y se cachea.
        """
        if self._resolved_site_id:
            return self._resolved_site_id

        if ":" not in self.site_id:
            self._resolved_site_id = self.site_id
            return self._resolved_site_id

        token = self.get_access_token()
        resolve_url = f"https://graph.microsoft.com/v1.0/sites/{self.site_id}"
        response = requests.get(
            resolve_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Error al resolver SHAREPOINT_SITE_ID ({response.status_code}): {response.text}"
            )

        self._resolved_site_id = response.json()["id"]
        return self._resolved_site_id

    def _get_drive_base_url(self) -> str:
        """
        Retorna la URL base del Drive en Graph API.
        Si DRIVE_ID está configurado lo utiliza; de lo contrario utiliza la biblioteca por defecto del sitio.
        """
        site_id = self._resolve_site_id()
        if self.drive_id:
            return f"https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{self.drive_id}"
        return f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive"

    def upload_file(self, file_bytes: io.BytesIO, filename: str, folder_path: Optional[str] = None, max_retries: int = 3) -> Dict[str, Any]:
        """
        Sube un archivo a SharePoint utilizando Microsoft Graph API.
        Reintenta ante errores transitorios de Graph (ej: 400 'root:' segment,
        429 throttling, 5xx) antes de propagar la excepción al llamador.
        """
        token = self.get_access_token()
        folder = folder_path.strip("/\\") if folder_path is not None else self.folder_path
        base_drive_url = self._get_drive_base_url()

        # Endpoint para subida de contenido en SharePoint
        if folder:
            upload_url = f"{base_drive_url}/root:/{folder}/{filename}:/content"
        else:
            upload_url = f"{base_drive_url}/root:/{filename}:/content"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

        # Asegurarse de leer los bytes desde el inicio
        file_bytes.seek(0)
        content = file_bytes.read()

        last_error: Optional[str] = None
        for attempt in range(1, max_retries + 1):
            response = requests.put(upload_url, headers=headers, data=content, timeout=60)
            if response.status_code in (200, 201):
                return response.json()

            last_error = f"({response.status_code}): {response.text}"
            # 429/5xx/400 'root:' suelen ser transitorios en Graph; reintentar con backoff
            if attempt < max_retries:
                time.sleep(1.5 * attempt)

        raise RuntimeError(f"Error al subir el archivo a SharePoint {last_error}")

    def share_file_with_emails(self, item_id: str, emails: List[str], role: str = "read") -> Dict[str, Any]:
        """
        Envía invitaciones de acceso en SharePoint a las direcciones de correo especificadas.
        """
        if not emails:
            return {"invited": False, "message": "No se especificaron correos"}

        token = self.get_access_token()
        base_drive_url = self._get_drive_base_url()
        invite_url = f"{base_drive_url}/items/{item_id}/invite"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        recipients = [{"email": e.strip()} for e in emails if e.strip()]
        if not recipients:
            return {"invited": False, "message": "Lista de correos vacía"}

        payload = {
            "recipients": recipients,
            "roles": [role],  # 'read' o 'write'
            "sendInvitation": True,
            "requireSignIn": True,
        }

        response = requests.post(invite_url, headers=headers, json=payload, timeout=30)
        if response.status_code not in (200, 201):
            print(f"Aviso al compartir en SharePoint con {emails}: {response.text}")
            return {"invited": False, "error": response.text}

        return response.json()

    def create_sharing_link(self, item_id: str, link_type: str = "view", scope: str = "organization") -> Optional[str]:
        """
        Crea un enlace de acceso compartido para el elemento (ej: acceso organización).
        """
        try:
            token = self.get_access_token()
            base_drive_url = self._get_drive_base_url()
            link_url = f"{base_drive_url}/items/{item_id}/createLink"

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            payload = {
                "type": link_type,    # 'view' o 'edit'
                "scope": scope,       # 'organization' o 'anonymous'
            }

            response = requests.post(link_url, headers=headers, json=payload, timeout=20)
            if response.status_code in (200, 201):
                data = response.json()
                return data.get("link", {}).get("webUrl")
        except Exception as e:
            print(f"Aviso al generar link compartido en SharePoint: {e}")
        return None

    def export_and_deliver(
        self,
        excel_buffer: io.BytesIO,
        filename: str,
        emails: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Método principal desacoplado:
        1. Si SharePoint está configurado: Sube el archivo, comparte con los correos y retorna el enlace.
        2. Si SharePoint NO está configurado: Guarda el archivo en la carpeta local 'generated_reports'
           y retorna la ruta local junto al aviso para que el usuario pueda usar el archivo de inmediato.
        """
        # Asegurarse que el archivo tenga extensión .xlsx
        if not filename.lower().endswith(".xlsx"):
            filename = f"{filename}.xlsx"

        if self.is_configured():
            try:
                # Subir archivo a SharePoint
                item = self.upload_file(excel_buffer, filename)
                item_id = item.get("id")
                web_url = item.get("webUrl")

                # Intentar compartir con correos si se proporcionaron
                if emails and item_id:
                    self.share_file_with_emails(item_id, emails, role="write")

                return {
                    "success": True,
                    "sheet_url": web_url,  # Mantiene retrocompatibilidad con frontend que lea sheet_url
                    "web_url": web_url,
                    "item_id": item_id,
                    "file_name": filename,
                    "storage": "sharepoint",
                    "message": "Archivo generado y subido a SharePoint con éxito.",
                }
            except Exception as e:
                print(f"Error al interactuar con SharePoint: {e}. Aplicando respaldo local.")
                # Si ocurre un error de red/credenciales con SharePoint, aplicar fallback local
                local_path = os.path.join(self.local_dir, filename)
                save_excel_to_disk(excel_buffer, local_path)
                return {
                    "success": True,
                    "sheet_url": os.path.abspath(local_path),
                    "web_url": None,
                    "local_path": os.path.abspath(local_path),
                    "file_name": filename,
                    "storage": "local_fallback",
                    "error_sharepoint": str(e),
                    "message": "Error al conectar con SharePoint. Archivo guardado localmente.",
                }
        else:
            # Modo local cuando las variables de SharePoint aún no están configuradas
            local_path = os.path.join(self.local_dir, filename)
            save_excel_to_disk(excel_buffer, local_path)
            return {
                "success": True,
                "sheet_url": os.path.abspath(local_path),
                "web_url": None,
                "local_path": os.path.abspath(local_path),
                "file_name": filename,
                "storage": "local",
                "message": "SharePoint aún no está configurado en .env. Archivo Excel generado y guardado localmente.",
            }

sharepoint_service = SharePointService()
