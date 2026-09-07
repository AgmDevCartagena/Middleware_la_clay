import os
from dotenv import load_dotenv

class Settings:
    def __init__(self):
       
        ## load variables of .env
        load_dotenv()
        self.PROJECT_NAME:str = "API gateway from ZEUS"
        self.PROJECT_VERSION:str = "0.0.1"

        ##
        self.SERVER:str = os.getenv("SERVER")
        self.USER:str = os.getenv("USER")
        self.PASSWORD:str = os.getenv("PASSWORD")
        self.PORT:str = os.getenv("PORT")
        self.DATABASE:str = os.getenv("DATABASE")
        self.DB_INVENTARIO:str = os.getenv("DB_INVENTARIO")
        self.DB_NOMINA:str = os.getenv("DB_NOMINA")
        self.DB_CONTABILIDAD:str = os.getenv("DB_CONTABILIDAD")

        self.DRIVER:str = os.getenv("DRIVER")

        ## Supabase 
        self.SUPABASE_URL=os.getenv("SUPABASE_URL")
        self.SUPABASE_KEY=os.getenv("SUPABASE_KEY")

        self.TOKEN_API=os.getenv("TOKEN_API")
        self.SERVICE_ACCOUNT=os.getenv("SERVICE_ACCOUNT")

        ## Microsoft SharePoint / Azure AD
        self.AZURE_TENANT_ID: str = os.getenv("AZURE_TENANT_ID", "")
        self.AZURE_CLIENT_ID: str = os.getenv("AZURE_CLIENT_ID", "")
        self.AZURE_CLIENT_SECRET: str = os.getenv("AZURE_CLIENT_SECRET", "")
        self.SHAREPOINT_SITE_ID: str = os.getenv("SHAREPOINT_SITE_ID", "")
        self.SHAREPOINT_DRIVE_ID: str = os.getenv("SHAREPOINT_DRIVE_ID", "")
        self.SHAREPOINT_FOLDER_PATH: str = os.getenv("SHAREPOINT_FOLDER_PATH", "Reportes")
        self.LOCAL_REPORTS_DIR: str = os.getenv("LOCAL_REPORTS_DIR", "generated_reports")

    def database_url(self,dbname:str = None ):
       if(dbname is None):
         str_conn=f"Driver={self.DRIVER};Server={self.SERVER};PORT={self.PORT};DATABASE={self.DATABASE};UID={self.USER};pwd={self.PASSWORD};TDS_Version=7.2;CHARSET=UTF-8;"
       else:
         str_conn=f"Driver={self.DRIVER};Server={self.SERVER};PORT={self.PORT};DATABASE={dbname};UID={self.USER};pwd={self.PASSWORD};TDS_Version=7.2;CHARSET=UTF-8;"
       return  str_conn
    def set_database(self,dbname:str):
        self.DATABASE:str=dbname

settings = Settings()