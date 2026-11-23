#!/bin/bash
#=============================================================================
#          FILE: install-eSim.sh
# 
#         USAGE: ./install-eSim.sh --install 
#                            OR
#                ./install-eSim.sh --uninstall
#                
#   DESCRIPTION: Installation script for eSim EDA Suite
#
#       OPTIONS: ---
#  REQUIREMENTS: ---
#          BUGS: ---
#         NOTES: ---
#       AUTHORS: Fahim Khan, Rahul Paknikar, Saurabh Bansode,
#                Sumanto Kar, Partha Singha Roy, Jayanth Tatineni,
#                Anshul Verma, Shiva Krishna Sangati, Harsha Narayana P
#  ORGANIZATION: eSim Team, FOSSEE, IIT Bombay
#       CREATED: Sunday 25 May 2025 17:40
#      REVISION: ---
#=============================================================================

# Variables used by the installer functions below.  The broken merge had
# dropped these definitions while pasting createConfigFile() into
# run_version_script(), so even a syntactically valid script would write to
# /config.ini and compute a wrong eSim home.
config_dir="$HOME/.esim"
config_file="config.ini"
eSim_Home="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Function to detect Ubuntu version and full version string
get_ubuntu_version() {
    # Read VERSION_ID directly from os-release.  lsb_release -d returns a
    # human-readable string such as "Ubuntu 25.04"; the old regex only matched
    # three-part versions (22.04.4) and silently produced an empty value on
    # Ubuntu 25.04, which broke every downstream version comparison.
    VERSION_ID=$(. /etc/os-release && echo "$VERSION_ID")
    FULL_VERSION=$(lsb_release -rs 2>/dev/null || true)
    if [[ -z "$FULL_VERSION" ]]; then
        FULL_VERSION="$VERSION_ID"
    fi
    echo "Detected Ubuntu Version: $VERSION_ID ($FULL_VERSION)"
}

# Function to choose and run the appropriate script
run_version_script() {
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/install-eSim-scripts"
    
    # Decide script based on full version
    case $VERSION_ID in
        "22.04")
            if [[ "$FULL_VERSION" == "22.04.4" ]]; then
                SCRIPT="$SCRIPT_DIR/install-eSim-22.04.sh"
            else
                SCRIPT="$SCRIPT_DIR/install-eSim-23.04.sh"
            fi
            ;;
        "23.04")
            SCRIPT="$SCRIPT_DIR/install-eSim-23.04.sh"
            ;;
        "24.04")
            SCRIPT="$SCRIPT_DIR/install-eSim-24.04.sh"
            ;;
        "25.04")
            # The released 2.5 zip predates Plucky.  Use the dedicated
            # 25.04 script when present, otherwise fall back to the 24.04
            # one (now patched to be Plucky-safe).
            if [[ -f "$SCRIPT_DIR/install-eSim-25.04.sh" ]]; then
                SCRIPT="$SCRIPT_DIR/install-eSim-25.04.sh"
            else
                SCRIPT="$SCRIPT_DIR/install-eSim-24.04.sh"
            fi
            ;;
        *)
            echo "Unsupported Ubuntu version: $VERSION_ID ($FULL_VERSION)"
            exit 1
            ;;
    esac

    # Run the script if found
    if [[ -f "$SCRIPT" ]]; then
        echo "Running script: $SCRIPT $ARGUMENT"
        bash "$SCRIPT" "$ARGUMENT"
    else
        echo "Installation script not found: $SCRIPT"
        exit 1
    fi
}

# --- Main Execution Starts Here ---

# Validate argument
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 --install | --uninstall"
    exit 1
fi

ARGUMENT=$1
if [[ "$ARGUMENT" != "--install" && "$ARGUMENT" != "--uninstall" ]]; then
    echo "Invalid argument: $ARGUMENT"
    echo "Usage: $0 --install | --uninstall"
    exit 1
fi

get_ubuntu_version
run_version_script
