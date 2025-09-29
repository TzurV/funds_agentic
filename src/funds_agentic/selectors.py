"""Centralized DOM selectors & heuristics.
If Trustnet changes its DOM, adjust here.
"""
# Cookie banner / consent
COOKIE_ALLOW_ALL = "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"
INVESTOR_LABEL = "label[for='tc-check-Investor']"
AGREE_BUTTON = "#tc-modal-agree"

# Sector performance page
SECTORS_URL = "https://www.trustnet.com/fund/sectors/performance?universe=O"
SECTORS_TABLE_CONTAINER = ".table-responsive"
SECTORS_HEADER_TOKEN = "Name"  # the header text that identifies the table we need
PAGINATION_BUTTONS = ".set-page"

# Fund pages
FUND_NAME = ".key-wrapper__fund-name"
FE_RISK = ".fe-fundinfo__riskscore"
TABLE_GENERIC = ".fe-table"
# presence check for the perf header line "3 m 6 m"
PERF_HEADER_TOKENS = ["3", "m", "6", "m"]
UNIT_INFO_TABLE = ".fe-table.fe_table__head-left.table-all-left"
SECTOR_LINK_TEXT = "(View sector)"
