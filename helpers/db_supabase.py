import os

from supabase import create_client, Client
from settings import settings
if settings.SUPABASE_URL and settings.SUPABASE_KEY:
    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
else:
    supabase = None

