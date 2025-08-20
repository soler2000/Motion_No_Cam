import os
DB_PATH = os.environ.get("MOTION_DB", "/opt/Motion_No_Cam/motion.db")
HOST = "0.0.0.0"
PORT = 8080
POLL_INTERVAL_S = 2