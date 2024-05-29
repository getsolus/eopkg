# bash utility functions
BOLD='\033[1m'
RED='\033[0;31m'
RESET='\033[0m'
YELLOW='\033[0;33m'

# Python venvs use the full python version. Solus uses 3.11 so prefer that
PY3="$(command -v python3.11 || command -v python3.12 || command -v python3.11)"

printInfo () {
    local INFO="${BOLD}INFO${RESET}"
    echo -e "${INFO} ${*}"
}

printWarning () {
    local WARNING="${YELLOW}${BOLD}WARNING${RESET}"
    echo -e "${WARNING} ${*}"
}

printError () {
    local ERROR="${RED}${BOLD}ERROR${RESET}"
    echo -e "${ERROR} ${*}"
}

showHelp() {
  # no-op in shell
  :
}

die() {
    printError "${*} failed, exiting.\n"
    showHelp
    exit 1
}
