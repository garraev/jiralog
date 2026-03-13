import os
from colorama import Fore, Back, Style, init
from dotenv import load_dotenv

load_dotenv()
init(autoreset=True)

RED, YEL, CYN, GRN, BLU = (
    Fore.LIGHTRED_EX, Fore.LIGHTYELLOW_EX, Fore.LIGHTCYAN_EX,
    Fore.LIGHTGREEN_EX, Fore.LIGHTBLUE_EX,
)
WHT  = Fore.LIGHTWHITE_EX
BOLD = Style.BRIGHT
BBLU = Back.BLUE
BRST = Back.RESET

JIRA_BASE_URL = os.environ.get('JIRA_BASE_URL')
JIRA_USERNAME = os.environ.get('JIRA_USERNAME')
JIRA_API_TOKEN = os.environ.get('JIRA_API_TOKEN')

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGS_DIR   = os.path.join(SCRIPT_DIR, 'logs')
REPORTS_DIR = os.path.join(SCRIPT_DIR, 'reports')
