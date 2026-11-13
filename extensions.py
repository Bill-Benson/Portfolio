from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Created here and attached to the app in server.py, so admin.py can use the
# same instances without importing server.
csrf = CSRFProtect()
limiter = Limiter(get_remote_address, default_limits=[])
