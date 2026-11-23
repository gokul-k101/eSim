# Steps taken for eSim Winter Internship 2026 — Task 4

Workspace (fresh, no reuse of existing folders): `/home/gokulk/esim-task4`

## 1. Read the task source
- Fetched the Google Doc via its export URL and extracted the Task 4 requirements: install eSim 2.5 on Ubuntu 25.04, list dependency problems, fix at least one in `install-eSim.sh`, fork the repo, checkout the installer branch, commit, and write a documented report.

## 2. Check the host environment
Command:
```
uname -a
cat /etc/os-release
git --version
curl --version | head -n 1
```
Result: `Ubuntu 25.04 (Plucky Puffin)`, kernel `6.14.0-37-generic`, git `2.48.1`, curl `8.12.1`. This machine itself is the required test platform, so no VM was needed.

## 3. Create a brand-new working folder and clone the repository fresh
Command:
```
mkdir -p /home/gokulk/esim-task4
git clone -b installers https://github.com/FOSSEE/eSim.git /home/gokulk/esim-task4/eSim
```
Note: the task says “installer branch”; the actual upstream branch is `installers` (there is no branch named `installer`). The clone is running in the background.

## 4. Download the official eSim 2.5 release archive
Command:
```
curl -fL -o eSim-2.5.zip https://static.fossee.in/esim/installation-files/eSim-2.5.zip
sha256sum eSim-2.5.zip
```
Result: SHA256 `b9860ae26f026930bae589520761f4a57b85d593a2e2cd1ac83d5e5db2f281ed`, which matches the checksum published on https://esim.fossee.in/downloads.

Command:
```
unzip -q eSim-2.5.zip -d eSim-2.5-release
```
Result: unpacked `eSim-2.5-release/eSim-2.5/` with `install-eSim.sh` and `install-eSim-scripts/install-eSim-2*.sh`.

## 5. Reproduce the first failure with the unmodified release installer
Commands:
```
chmod +x install-eSim.sh install-eSim-scripts/*.sh
printf 'n\n' | ./install-eSim.sh --install 2>&1 | tee logs/00-baseline.log
```
Output (log `logs/00-baseline.log`):
```
Detected Ubuntu Version: 
Unsupported Ubuntu version: 25.04 ()
```
Two defects are visible at once:
1. `install-eSim.sh` has no `25.04` case in its version dispatcher.
2. `FULL_VERSION=$(lsb_release -d | grep -oP '\d+\.\d+\.\d+')` only matches a three-part version, so on 25.04 it is empty (Ubuntu reports `25.04`, not `25.04.0`).

## 6. Inspect the shipped install scripts
- `install-eSim-scripts/install-eSim-24.04.sh` (456 lines) is the newest per-version script in the 2.5 release zip.
- Its `installKicad()` only recognises `24.04`; on `25.04` it falls into the `else` branch and adds the obsolete `kicad/kicad-6.0-releases` PPA.
- Its `copyKicadLibrary()` hard-codes `~/.config/kicad/6.0` while Ubuntu 25.04 ships KiCad 8.0.
- The bundled `nghdl.zip` installer (`install-nghdl.sh`) also has no `25.04` case, so NgSpice/GHDL installation aborts even after the eSim dispatcher is fixed.

## 7. Investigate the “stuck at LLVM” failure
Commands:
```
unzip -o -q nghdl.zip -d nghdl
mkdir -p diagnostic
tar -xzf nghdl/nghdl/ghdl-4.1.0.tar.gz -C diagnostic
cd diagnostic/ghdl-4.1.0 && ./configure --with-llvm-config=/usr/bin/llvm-config
grep -n 'check_version' configure
apt-cache policy llvm llvm-18-dev
```
Findings:
- GHDL 4.1.0’s `configure` accepts LLVM only through `18.1` (`configure` lines 299–326) and exits with `Unhandled version llvm <version>` otherwise.
- Ubuntu 25.04’s default `llvm-dev` candidate is `1:20.0-63ubuntu1`, so `./configure --with-llvm-config=/usr/bin/llvm-config` hits exactly that unsupported-version exit. `llvm-18`, `llvm-18-dev`, and `llvm-18-tools` are available (`1:18.1.8-17`) in Plucky.
- The first configure probe also reported `Sorry, you need GNAT to build GHDL` because GNAT is not installed on this host and passwordless `sudo` is unavailable; the package checks were therefore done with `apt-cache` rather than a privileged full install.

## 8. Inspect the upstream `installers` branch scripts
Fetched the raw files from GitHub (to compare against the release zip):
- `Ubuntu/install-eSim.sh` already contains a `25.04` case pointing to `install-eSim-25.04.sh`.
- `Ubuntu/install-eSim-scripts/install-eSim-25.04.sh` pins `kicad=8.0.8+dfsg-1` (confirmed available on Plucky) but still hard-codes the KiCad 6.0 config directory.
- `Ubuntu/install-eSim-scripts/install-eSim-24.04.sh` on that branch tries `sudo apt-get install -y python3-distutils`; `apt-cache policy python3-distutils` on 25.04 returns `Candidate: (none)` because Python 3.13 removed distutils. With `set -e`, this aborts the install.

## 9. Write and validate the fix script
Created `apply_fixes.py`, which patches either the release tree or an `installers`-branch checkout:
- version detection + `25.04` dispatcher case in `install-eSim.sh`;
- idempotent `configureNgHdlForPlucky` helper that adds a `25.04` case to the bundled NGHDL dispatcher, pins `llvm-18 llvm-18-dev llvm-18-tools`, and switches GHDL to `/usr/bin/llvm-config-18`;
- guard around the unavailable `python3-distutils` package;
- dynamic KiCad config-directory detection instead of hard-coded `6.0`.

Validation commands:
```
python3 apply_fixes.py eSim-2.5-test/eSim-2.5
bash -n install-eSim.sh
for f in install-eSim-scripts/*.sh; do bash -n "$f"; done
```
All scripts pass `bash -n`. An isolated extraction of `nghdl.zip` plus the helper produced a valid `install-nghdl.sh` containing the `25.04` case and an `install-nghdl-24.04.sh` containing `llvm-18` and `llvm-config-18`.

## 10. Re-run the patched dispatcher
```
printf 'n\n' | ./install-eSim.sh --install
```
Output:
```
Detected Ubuntu Version: 25.04 (25.04)
Running script: .../install-eSim-scripts/install-eSim-25.04.sh --install
```
The run then stops at the first `sudo` prompt because this shell has no passwordless sudo; the privileged `apt`/`make install` portion cannot be completed here. Everything up to that point is verified.

## 11. Write the deliverable report
Created `REPORT.md` with the environment, five issues (symptom, evidence, root cause, fix), verification notes, the sudo limitation, and the list of changed files. It will be copied into the freshly cloned repository alongside a local commit.

## 12. Clone finishes; run the installer directly from the fresh clone
```
git -C eSim branch --show-current     # installers
git -C eSim log -1 --oneline          # a77d6b90 Merge pull request #414 ...
printf 'n\n' | ./Ubuntu/install-eSim.sh --install
```
Output:
```
./Ubuntu/install-eSim.sh: line 70: syntax error near unexpected token `}'
./Ubuntu/install-eSim.sh: line 70: `}'
```
This is a genuine upstream bug: a broken merge pasted `createConfigFile()`'s body into `run_version_script()` and dropped the script's variables. (There is no `install-eSim.sh` at the repository root; the task's `./install-eSim.sh` corresponds to the script inside the release zip and to `Ubuntu/install-eSim.sh` in this branch.)

## 13. Repair the merge damage and apply all fixes to the clone
```
python3 apply_fixes.py eSim
chmod +x eSim/Ubuntu/install-eSim.sh eSim/Ubuntu/install-eSim-scripts/*.sh
```
`apply_fixes.py` now also restores `config_dir`, `config_file`, and `eSim_Home`, closes the broken `if` with `else`/`fi`, and recreates `createConfigFile()`.

## 14. Run the patched installer from the clone
```
printf 'n\n' | timeout 60s bash ./Ubuntu/install-eSim.sh --install
```
Output:
```
Detected Ubuntu Version: 25.04 (25.04)
Running script: .../Ubuntu/install-eSim-scripts/install-eSim-25.04.sh --install
...
sudo: a password is required
```
The installer now parses, detects Plucky correctly, dispatches to the 25.04 script, and stops only at the privileged `apt` step because this shell has no passwordless sudo.

## 15. Add a repeatable verification script
Created `verify.sh`; it checks syntax, dispatcher logic, the distutils guard, NGHDL/LLVM fixes, KiCad config detection, and the live version-detection output. Result: `ALL CHECKS PASSED`.

## 16. Commit in the fresh clone
```
git config user.name "eSim Task 4 Contributor"
git config user.email "esim-task4@localhost"
git add Ubuntu/install-eSim.sh Ubuntu/install-eSim-scripts REPORT.md STEPS.md verify.sh
git commit -m "Fix eSim 2.5 installer for Ubuntu 25.04 and document findings"
```
Result: local commit `54727e20` on branch `installers`; working tree clean. Creating a GitHub fork and pushing requires GitHub credentials, which are not available in this environment, so that submission step is left for the account owner.

## 17. Clarify the plain-user path for 2.5 on 25.04
The user clarified they wanted to know how a normal person installs 2.5 on 25.04 without repo work. The answer: a zero-change install is impossible because the official 2.5 installer hard-rejects 25.04. The human path is to download the official zip, copy it to a local folder, manually edit the extracted scripts (dispatcher `25.04` case, NGHDL `25.04` case, LLVM 18 pin, KiCad 8 PPA/config path), then run `./install-eSim.sh --install` with sudo. No git clone, fork, or commit is needed for that path.

## 18. Close a missed KiCad PPA gap in the patcher
While writing the manual instructions, I noticed the 24.04-derived 25.04 script still had `if [[ "$ubuntu_version" == "24.04" ]]` in `installKicad()`, which would add the obsolete KiCad 6 PPA on Plucky. Extended `apply_fixes.py` to treat 25.04 like 24.04 there and to remove the hard-coded `~/.config/kicad/6.0` uninstall path. Re-ran the patcher on both the release copy and the clone; all scripts still pass `bash -n`. `verify.sh` now checks the PPA branch too.

## 19. Diagnose the user's failed install
After the user ran the patched installer manually:
- `~/.esim/env` existed and contained all pip packages, but `/usr/bin/esim`, `~/Desktop/esim.desktop`, and `/usr/share/applications/esim.desktop` did not.
- `nghdl.zip` had not even been extracted and the SKY130 PDK was absent, so the installer stopped before those steps.
- `dpkg -s kicad` showed KiCad 8 was already installed. Inspecting `installKicad()` revealed an `exit 0` in the "KiCad 8.0 is already installed" branch, which terminated the entire installer early with a success status.

## 20. Fix the early exit
Replaced that `exit 0` with `return 0` in both per-version scripts via `apply_fixes.py`. Also documented the volare pip warning and the explicit fix:
```
source ~/.esim/env/bin/activate
pip install "pyyaml>=5,<7" "rich>=12,<14"
```
Re-ran `bash -n`, `verify.sh`, and amended the local commit.
