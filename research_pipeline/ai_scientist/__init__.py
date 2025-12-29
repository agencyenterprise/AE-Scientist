from dotenv import load_dotenv

from .sentry_config import init_sentry

# Load environment variables from .env file
# This will look for .env in the current directory and parent directories
load_dotenv()
init_sentry()
