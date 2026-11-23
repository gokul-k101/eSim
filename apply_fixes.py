#!/usr/bin/env python3
"""Apply Task 4 fixes to an eSim checkout (installers branch) or release tree.

Usage: python3 apply_fixes.py <path-to-eSim-tree>
"""
from pathlib import Path
import re
import sys

OLD_GET_VERSION = '''get_ubuntu_version() {
    VERSION_ID=$(grep "^VERSION_ID" /etc/os-release | cut -d '"' -f 2)
    FULL_VERSION=$(lsb_release -d | grep -oP '\\d+\\.\\d+\\.\\d+')
    echo "Detected Ubuntu Version: $FULL_VERSION"
}'''

NEW_GET_VERSION = '''get_ubuntu_version() {
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
}'''

OLD_24_CASE = '''        "24.04")
            SCRIPT="$SCRIPT_DIR/install-eSim-24.04.sh"
            ;;
        *)'''

NEW_24_CASE = '''        "24.04")
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
        *)'''

NGHDL_FUNC = """
# Ubuntu 25.04 ships LLVM 20 by default, but the GHDL 4.1.0 source bundled
# with eSim 2.5 only understands LLVM <= 18.1.  Patch the extracted NGHDL
# installer in-place so it selects LLVM 18 and also teaches its dispatcher
# about Plucky.  Both edits are idempotent.
function configureNgHdlForPlucky
{
    local dispatcher="nghdl/install-nghdl.sh"
    local plucky_script="nghdl/install-nghdl-scripts/install-nghdl-24.04.sh"

    if [[ ! -f "$dispatcher" || ! -f "$plucky_script" ]]; then
        echo "NGHDL installer files not found; skipping Plucky adjustments"
        return 0
    fi

    if ! grep -q '"25.04"' "$dispatcher"; then
        python3 - "$dispatcher" <<'PYEOF'
import sys
path = sys.argv[1]
with open(path) as fh:
    text = fh.read()
needle = '''        "24.04")
            SCRIPT="$SCRIPT_DIR/install-nghdl-24.04.sh"
            ;;
'''
replacement = needle + '''        "25.04")
            SCRIPT="$SCRIPT_DIR/install-nghdl-24.04.sh"
            ;;
'''
if needle not in text:
    raise SystemExit("NGHDL 24.04 case not found")
with open(path, "w") as fh:
    fh.write(text.replace(needle, replacement, 1))
PYEOF
        echo "Patched NGHDL version dispatcher for Ubuntu 25.04"
    fi

    if grep -q 'apt install -y llvm llvm-dev' "$plucky_script"; then
        sed -i 's/apt install -y llvm llvm-dev/apt install -y llvm-18 llvm-18-dev llvm-18-tools/' "$plucky_script"
        echo "Pinned NGHDL LLVM dependencies to LLVM 18"
    fi

    if grep -q -- '--with-llvm-config=/usr/bin/llvm-config$' "$plucky_script"; then
        sed -i 's#--with-llvm-config=/usr/bin/llvm-config$#--with-llvm-config=/usr/bin/llvm-config-18#' "$plucky_script"
        echo "Pointed GHDL configure at llvm-config-18"
    fi
}

"""

OLD_UNZIP = '''    echo "Installing NGHDL..........................."
    unzip -o nghdl.zip
    cd nghdl/'''

NEW_UNZIP = '''    echo "Installing NGHDL..........................."
    unzip -o nghdl.zip
    configureNgHdlForPlucky
    cd nghdl/'''

OLD_KICAD_VERSION = '    if [[ "$ubuntu_version" == "24.04" ]]; then'
NEW_KICAD_VERSION = '    if [[ "$ubuntu_version" == "24.04" || "$ubuntu_version" == "25.04" ]]; then'

OLD_KICAD_EARLY_EXIT = '''            else
                echo "KiCad 8.0 is already installed."
                exit 0
            fi'''
NEW_KICAD_EARLY_EXIT = '''            else
                echo "KiCad 8.0 is already installed."
                return 0
            fi'''

OLD_UNINSTALL_KICAD = '        rm -rf $HOME/.config/kicad/6.0'
NEW_UNINSTALL_KICAD = '''        kicad_config_dir="$HOME/.config/kicad"
        latest_version=$(ls "$kicad_config_dir" 2>/dev/null | grep -E '^[0-9]+\\.[0-9]+$' | sort -V | tail -n 1)
        if [ -n "$latest_version" ]; then
            rm -rf "$kicad_config_dir/$latest_version"
        fi'''

OLD_KICAD_CFG = '''    if [ -d ~/.config/kicad/6.0 ];then
        echo "kicad config folder already exists"
    else 
        echo ".config/kicad/6.0 does not exist"
        mkdir -p ~/.config/kicad/6.0
    fi

    # Copy symbol table for eSim custom symbols 
    cp kicadLibrary/template/sym-lib-table ~/.config/kicad/6.0/'''

NEW_KICAD_CFG = '''    # Ubuntu 25.04 ships KiCad 8, so the old hard-coded 6.0 config path
    # silently installed eSim's symbol table into a directory KiCad never
    # reads.  Discover the newest installed config directory instead.
    kicad_config_dir="$HOME/.config/kicad"
    latest_version=$(ls "$kicad_config_dir" 2>/dev/null | grep -E '^[0-9]+\\.[0-9]+$' | sort -V | tail -n 1)
    if [ -z "$latest_version" ]; then
        latest_version="8.0"
    fi
    mkdir -p "$kicad_config_dir/$latest_version"

    # Copy symbol table for eSim custom symbols
    cp kicadLibrary/template/sym-lib-table "$kicad_config_dir/$latest_version/"'''

OLD_DISTUTILS = '''    echo "Installing Distutils......................."
    sudo apt-get install -y python3-distutils'''

HEADER_ANCHOR = '#=============================================================================\n\n# Function to detect Ubuntu version and full version string'

SCRIPT_VARS = '''#=============================================================================

# Variables used by the installer functions below.  The broken merge had
# dropped these definitions while pasting createConfigFile() into
# run_version_script(), so even a syntactically valid script would write to
# /config.ini and compute a wrong eSim home.
config_dir="$HOME/.esim"
config_file="config.ini"
eSim_Home="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Function to detect Ubuntu version and full version string'''

OLD_BROKEN_RUNNER = '''    if [[ -f "$SCRIPT" ]]; then
        echo "Running script: $SCRIPT $ARGUMENT"
        bash "$SCRIPT" "$ARGUMENT"
    echo "[eSim]" >> $config_dir/$config_file
    echo "eSim_HOME = $eSim_Home" >> $config_dir/$config_file
    echo "LICENSE = %(eSim_HOME)s/LICENSE" >> $config_dir/$config_file
    echo "KicadLib = %(eSim_HOME)s/library/kicadLibrary.tar.xz" >> $config_dir/$config_file
    echo "IMAGES = %(eSim_HOME)s/images" >> $config_dir/$config_file
    echo "VERSION = %(eSim_HOME)s/VERSION" >> $config_dir/$config_file
    echo "MODELICA_MAP_JSON = %(eSim_HOME)s/library/ngspicetoModelica/Mapping.json" >> $config_dir/$config_file
   
}
'''

NEW_RUNNER = '''    if [[ -f "$SCRIPT" ]]; then
        echo "Running script: $SCRIPT $ARGUMENT"
        bash "$SCRIPT" "$ARGUMENT"
    else
        echo "Installation script not found: $SCRIPT"
        exit 1
    fi
}

function createConfigFile
{
    if [ -d "$config_dir" ]; then
        rm -f "$config_dir/$config_file"
    else
        mkdir -p "$config_dir"
    fi
    touch "$config_dir/$config_file"

    echo "[eSim]" >> "$config_dir/$config_file"
    echo "eSim_HOME = $eSim_Home" >> "$config_dir/$config_file"
    echo "LICENSE = %(eSim_HOME)s/LICENSE" >> "$config_dir/$config_file"
    echo "KicadLib = %(eSim_HOME)s/library/kicadLibrary.tar.xz" >> "$config_dir/$config_file"
    echo "IMAGES = %(eSim_HOME)s/images" >> "$config_dir/$config_file"
    echo "VERSION = %(eSim_HOME)s/VERSION" >> "$config_dir/$config_file"
    echo "MODELICA_MAP_JSON = %(eSim_HOME)s/library/ngspicetoModelica/Mapping.json" >> "$config_dir/$config_file"
}
'''

NEW_DISTUTILS = '''    # python3-distutils was removed in Ubuntu 25.04 (Python 3.13).  With
    # set -e, a bare apt install aborts the whole installation.  Only install
    # it on releases where the package actually exists.
    if apt-cache show python3-distutils >/dev/null 2>&1; then
        echo "Installing Distutils......................."
        sudo apt-get install -y python3-distutils
    else
        echo "python3-distutils is unavailable on this release; skipping"
    fi'''

MARKER = "####################################################################\n#                   MAIN START FROM HERE                           #"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        print(f"  SKIP {label}: pattern not present")
        return text
    print(f"  PATCH {label}")
    return text.replace(old, new, 1)


def main() -> None:
    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        sys.exit(f"Not a directory: {root}")

    # Release zip has scripts at the root; installers branch has Ubuntu/.
    base = root / "Ubuntu" if (root / "Ubuntu" / "install-eSim.sh").exists() else root
    scripts = base / "install-eSim-scripts"

    print(f"Patching {base}")

    dispatcher = base / "install-eSim.sh"
    text = dispatcher.read_text()
    text = replace_once(text, OLD_GET_VERSION, NEW_GET_VERSION, "version detection")
    text = replace_once(text, OLD_24_CASE, NEW_24_CASE, "25.04 dispatcher case")
    text = replace_once(text, HEADER_ANCHOR, SCRIPT_VARS, "restore installer variables")
    text = replace_once(text, OLD_BROKEN_RUNNER, NEW_RUNNER, "repair broken dispatcher merge")
    text = replace_once(text, OLD_DISTUTILS, NEW_DISTUTILS, "dispatcher: distutils guard")
    text = replace_once(text, OLD_UNZIP, NEW_UNZIP, "dispatcher: call Plucky NGHDL fix")
    if MARKER in text and "function configureNgHdlForPlucky" not in text:
        print("  PATCH dispatcher: add NGHDL helper")
        text = text.replace(MARKER, NGHDL_FUNC + MARKER, 1)
    dispatcher.write_text(text)

    # Release zip has no 25.04 script: create one from the 24.04 script.
    target_25 = scripts / "install-eSim-25.04.sh"
    if not target_25.exists():
        print("  CREATE install-eSim-25.04.sh from 24.04 script")
        target_25.write_text((scripts / "install-eSim-24.04.sh").read_text())

    for name in ("install-eSim-24.04.sh", "install-eSim-25.04.sh"):
        path = scripts / name
        text = path.read_text()
        text = replace_once(text, OLD_DISTUTILS, NEW_DISTUTILS, f"{name}: distutils guard")
        text = replace_once(text, OLD_UNZIP, NEW_UNZIP, f"{name}: call Plucky NGHDL fix")
        if MARKER in text and "function configureNgHdlForPlucky" not in text:
            print(f"  PATCH {name}: add NGHDL helper")
            text = text.replace(MARKER, NGHDL_FUNC + MARKER, 1)
        text = replace_once(text, OLD_KICAD_CFG, NEW_KICAD_CFG, f"{name}: KiCad config directory")
        text = replace_once(text, OLD_KICAD_VERSION, NEW_KICAD_VERSION, f"{name}: KiCad PPA version check")
        text = replace_once(text, OLD_KICAD_EARLY_EXIT, NEW_KICAD_EARLY_EXIT, f"{name}: KiCad already-installed exit")
        text = replace_once(text, OLD_UNINSTALL_KICAD, NEW_UNINSTALL_KICAD, f"{name}: KiCad uninstall path")
        path.write_text(text)

    print("Done.")


if __name__ == "__main__":
    main()
