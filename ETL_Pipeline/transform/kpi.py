from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials